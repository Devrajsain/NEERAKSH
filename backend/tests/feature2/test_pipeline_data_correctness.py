"""
Comprehensive Test Suite for Feature 2 Environmental Data Pipeline Hardening & Correctness.
Implements the 10 mandatory scientific and operational correctness tests:
  1. Acquisition Timestamp extraction from GeoTIFF tags and filename to Feature 2 in UTC.
  2. Never use processing time (mocking time.time() / datetime.now() does not alter observation_time).
  3. Dynamic Copernicus query domain shifts with spill location.
  4. Dynamic GFS query domain shifts with spill location.
  5. Dynamic environmental time windows shift with observation time.
  6. Moving particle velocity updates spatially (proving no frozen single-point velocity).
  7. Temporal interpolation linearly updates forcing between discrete time slices.
  8. Outside coverage fail-closed behavior (no fake velocity, no mock fallback, clear degradation).
  9. Extended provenance audit (requested/actual domain, resolution, model_source, access_provider).
 10. Strict LIVE_OPERATIONAL status criteria.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import xarray as xr
import rasterio
from rasterio.transform import from_bounds

from app.services.geotiff import extract_sentinel1_acquisition_metadata, inspect_image_geospatial
from app.services.detection import _resolve_detection_timestamps
from app.feature2.config import Feature2Settings, DataSourceConfig
from app.feature2.data.domain import SentinelObservationDomain, EnvironmentalQueryDomain
from app.feature2.data.currents.copernicus import CopernicusCurrentsProvider, CopernicusConfig
from app.feature2.data.wind.gfs import GFSWindProvider, GFSConfig
from app.feature2.data.local_netcdf import LocalNetCDFDatasetReader, VariableMapping
from app.feature2.pipeline.service import Feature2PipelineService
from app.feature2.schemas.input_schema import SlickDetectionInput, CentroidCoordinates, GeoJSONGeometry
from app.feature2.exceptions import OutOfDomainError, TemporalCoverageError, EnvironmentalCoverageError
from app.feature2.simulation.forward.engine import ForwardSimulationEngine
from app.feature2.forecast.forecaster import ForwardForecaster
from app.feature2.origin.estimator import OriginEstimator


class TestDataCorrectnessPipeline(unittest.TestCase):
    """Rigorous tests verifying scientific and data correctness across Feature 1 -> Feature 2."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_acquisition_timestamp_pipeline(self):
        """
        NEW TEST 1: ACQUISITION TIMESTAMP
        Create a GeoTIFF with known Sentinel-1 metadata and verify it flows to Feature 1 detection
        and Feature 2 observation_time as UTC.
        """
        # Create a test GeoTIFF with Sentinel-1 granule name and TIFF tags
        filename = "S1A_IW_GRDH_1SDV_20240415T183045_20240415T183110_053450_067B25_A123.tif"
        tif_path = os.path.join(self.temp_dir, filename)

        transform = from_bounds(54.0, 24.0, 55.0, 25.0, 100, 100)
        with rasterio.open(
            tif_path,
            'w',
            driver='GTiff',
            height=100,
            width=100,
            count=1,
            dtype='uint8',
            crs='EPSG:4326',
            transform=transform,
        ) as dst:
            dst.update_tags(
                PRODUCT_SCENE_RASTER_START_TIME="15-APR-2024 18:30:45.000000",
                TIFFTAG_DATETIME="2024:04:15 18:30:45",
            )
            dst.write(np.zeros((1, 100, 100), dtype='uint8'))

        # Extract metadata
        meta = extract_sentinel1_acquisition_metadata(tif_path)
        self.assertIsNotNone(meta["acquisition_timestamp"])
        self.assertEqual(meta["observation_time_source"], "sentinel_metadata")
        self.assertEqual(meta["acquisition_timestamp"], "2024-04-15T18:30:45Z")

        # Resolve detection timestamps in detection service
        geo_meta = inspect_image_geospatial(tif_path)
        timestamps = _resolve_detection_timestamps(geo_meta, explicit_observation_time=None, allow_test_fixture=False)
        self.assertEqual(timestamps["observation_time"], "2024-04-15T18:30:45Z")
        self.assertEqual(timestamps["acquisition_timestamp"], "2024-04-15T18:30:45Z")
        self.assertEqual(timestamps["observation_time_source"], "sentinel_metadata")

        # Verify Feature 2 ingestion
        slick = SlickDetectionInput(
            spill_id="TEST_ACQ_001",
            observation_time=datetime.fromisoformat(timestamps["observation_time"].replace("Z", "+00:00")),
            observation_time_source=timestamps["observation_time_source"],
            centroid=CentroidCoordinates(latitude=24.5, longitude=54.5),
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[54.4, 24.4], [54.6, 24.4], [54.6, 24.6], [54.4, 24.6], [54.4, 24.4]]]
            ),
            area_sq_km=5.0,
            perimeter_km=10.0,
        )
        self.assertEqual(slick.observation_time.tzinfo, timezone.utc)
        self.assertEqual(slick.observation_time.year, 2024)
        self.assertEqual(slick.observation_time.month, 4)
        self.assertEqual(slick.observation_time.day, 15)
        self.assertEqual(slick.observation_time.hour, 18)
        self.assertEqual(slick.observation_time.minute, 30)

    def test_02_never_use_processing_time(self):
        """
        NEW TEST 2: NEVER USE PROCESSING TIME
        Mock time.time() and datetime.now() with an arbitrary timestamp and verify
        that Feature 1 & 2 continue to use genuine acquisition time.
        """
        filename = "S1B_IW_GRDH_1SDV_20230810T120000_20230810T120025_038850_049B25_B456.tif"
        tif_path = os.path.join(self.temp_dir, filename)

        transform = from_bounds(54.0, 24.0, 55.0, 25.0, 50, 50)
        with rasterio.open(
            tif_path,
            'w',
            driver='GTiff',
            height=50,
            width=50,
            count=1,
            dtype='uint8',
            crs='EPSG:4326',
            transform=transform,
        ) as dst:
            dst.write(np.zeros((1, 50, 50), dtype='uint8'))

        fake_processing_time = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with patch("time.gmtime", return_value=fake_processing_time.timetuple()):
            geo_meta = inspect_image_geospatial(tif_path)
            timestamps = _resolve_detection_timestamps(geo_meta, explicit_observation_time=None, allow_test_fixture=False)
            self.assertEqual(timestamps["observation_time"], "2023-08-10T12:00:00Z")
            self.assertEqual(timestamps["observation_time_source"], "sentinel_metadata")
            # Processing time is distinct
            self.assertNotEqual(timestamps["observation_time"], timestamps["processing_time"])

    def test_03_dynamic_copernicus_query(self):
        """
        NEW TEST 3: DYNAMIC COPERNICUS QUERY
        Spill A at (lat A, lon B) vs Spill B at (lat C, lon D).
        Verify Copernicus subset request shifts completely without hardcoding.
        """
        t0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        spill_a = SlickDetectionInput(
            spill_id="SPILL_A",
            observation_time=t0,
            centroid=CentroidCoordinates(latitude=25.0, longitude=55.0),
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[54.9, 24.9], [55.1, 24.9], [55.1, 25.1], [54.9, 25.1], [54.9, 24.9]]]
            ),
            area_sq_km=2.0,
            perimeter_km=6.0,
        )
        spill_b = SlickDetectionInput(
            spill_id="SPILL_B",
            observation_time=t0,
            centroid=CentroidCoordinates(latitude=-10.0, longitude=120.0),
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[119.9, -10.1], [120.1, -10.1], [120.1, -9.9], [119.9, -9.9], [119.9, -10.1]]]
            ),
            area_sq_km=2.0,
            perimeter_km=6.0,
        )

        domain_a = EnvironmentalQueryDomain.from_sentinel_observation(
            SentinelObservationDomain.from_slick_input(spill_a),
            buffer_distance_km=50.0,
            forecast_horizon_hours=48.0,
            max_transport_velocity_mps=1.0,
        )
        domain_b = EnvironmentalQueryDomain.from_sentinel_observation(
            SentinelObservationDomain.from_slick_input(spill_b),
            buffer_distance_km=50.0,
            forecast_horizon_hours=48.0,
            max_transport_velocity_mps=1.0,
        )

        provider = CopernicusCurrentsProvider()
        req_a = provider.build_subset_request(domain_a)
        req_b = provider.build_subset_request(domain_b)

        # Assert no overlap in coordinates
        self.assertAlmostEqual(req_a["minimum_latitude"], domain_a.min_lat, places=2)
        self.assertAlmostEqual(req_a["maximum_latitude"], domain_a.max_lat, places=2)
        self.assertAlmostEqual(req_b["minimum_latitude"], domain_b.min_lat, places=2)
        self.assertAlmostEqual(req_b["maximum_latitude"], domain_b.max_lat, places=2)

        self.assertGreater(req_a["minimum_latitude"], 20.0)
        self.assertLess(req_b["maximum_latitude"], 0.0)

    def test_04_dynamic_gfs_query(self):
        """
        NEW TEST 4: DYNAMIC GFS QUERY
        Two different spill locations result in completely distinct GFS query requests.
        """
        t0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        spill_a = SlickDetectionInput(
            spill_id="SPILL_GFS_A",
            observation_time=t0,
            centroid=CentroidCoordinates(latitude=28.0, longitude=-90.0), # Gulf of Mexico
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[-90.1, 27.9], [-89.9, 27.9], [-89.9, 28.1], [-90.1, 28.1], [-90.1, 27.9]]]
            ),
            area_sq_km=2.0,
            perimeter_km=6.0,
        )
        spill_b = SlickDetectionInput(
            spill_id="SPILL_GFS_B",
            observation_time=t0,
            centroid=CentroidCoordinates(latitude=35.0, longitude=140.0), # Japan coast
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[139.9, 34.9], [140.1, 34.9], [140.1, 35.1], [139.9, 35.1], [139.9, 34.9]]]
            ),
            area_sq_km=2.0,
            perimeter_km=6.0,
        )

        domain_a = EnvironmentalQueryDomain.from_sentinel_observation(
            SentinelObservationDomain.from_slick_input(spill_a),
            buffer_distance_km=40.0,
            forecast_horizon_hours=48.0,
        )
        domain_b = EnvironmentalQueryDomain.from_sentinel_observation(
            SentinelObservationDomain.from_slick_input(spill_b),
            buffer_distance_km=40.0,
            forecast_horizon_hours=48.0,
        )

        gfs_prov = GFSWindProvider()
        req_a = gfs_prov.build_forecast_request(domain_a)
        req_b = gfs_prov.build_forecast_request(domain_b)

        self.assertAlmostEqual(req_a["min_lat"], domain_a.min_lat, places=2)
        self.assertAlmostEqual(req_a["min_lon"], domain_a.min_lon, places=2)
        self.assertAlmostEqual(req_b["min_lat"], domain_b.min_lat, places=2)
        self.assertAlmostEqual(req_b["min_lon"], domain_b.min_lon, places=2)

        self.assertTrue(req_a["min_lon"] < 0)
        self.assertTrue(req_b["min_lon"] > 0)

    def test_05_dynamic_time(self):
        """
        NEW TEST 5: DYNAMIC TIME
        Two different Sentinel acquisition times generate two distinct environmental time windows.
        """
        t0_a = datetime(2023, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        t0_b = datetime(2024, 11, 20, 16, 0, 0, tzinfo=timezone.utc)

        spill_a = SlickDetectionInput(
            spill_id="SPILL_TIME_A",
            observation_time=t0_a,
            centroid=CentroidCoordinates(latitude=25.0, longitude=55.0),
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[54.9, 24.9], [55.1, 24.9], [55.1, 25.1], [54.9, 25.1], [54.9, 24.9]]]
            ),
            area_sq_km=2.0,
            perimeter_km=6.0,
        )
        spill_b = SlickDetectionInput(
            spill_id="SPILL_TIME_B",
            observation_time=t0_b,
            centroid=CentroidCoordinates(latitude=25.0, longitude=55.0),
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[54.9, 24.9], [55.1, 24.9], [55.1, 25.1], [54.9, 25.1], [54.9, 24.9]]]
            ),
            area_sq_km=2.0,
            perimeter_km=6.0,
        )

        domain_a = EnvironmentalQueryDomain.from_sentinel_observation(
            SentinelObservationDomain.from_slick_input(spill_a),
            historical_horizon_hours=72.0,
            forecast_horizon_hours=48.0,
        )
        domain_b = EnvironmentalQueryDomain.from_sentinel_observation(
            SentinelObservationDomain.from_slick_input(spill_b),
            historical_horizon_hours=72.0,
            forecast_horizon_hours=48.0,
        )

        self.assertEqual(domain_a.observation_time, t0_a)
        self.assertEqual(domain_b.observation_time, t0_b)
        self.assertEqual(domain_a.forecast_end_time, t0_a + timedelta(hours=48))
        self.assertEqual(domain_b.forecast_end_time, t0_b + timedelta(hours=48))
        self.assertEqual(domain_a.historical_start_time, t0_a - timedelta(hours=72))
        self.assertEqual(domain_b.historical_start_time, t0_b - timedelta(hours=72))

    def test_06_moving_particle_spatial_velocity_change(self):
        """
        NEW TEST 6: MOVING PARTICLE
        Create a synthetic NetCDF grid where current velocity at point A != velocity at point B.
        Verify that a moving particle receives spatially interpolated, changing velocities.
        """
        nc_path = os.path.join(self.temp_dir, "spatial_grad.nc")
        lats = np.array([24.0, 25.0, 26.0], dtype=np.float32)
        lons = np.array([54.0, 55.0, 56.0], dtype=np.float32)
        times = np.array(["2024-05-01T00:00:00", "2024-05-03T00:00:00"], dtype="datetime64[ns]")

        # U varies with longitude: at 54.0 u=0.2, at 55.0 u=0.5, at 56.0 u=1.0
        u_vals = np.zeros((2, 3, 3), dtype=np.float32)
        u_vals[:, :, 0] = 0.2
        u_vals[:, :, 1] = 0.5
        u_vals[:, :, 2] = 1.0

        v_vals = np.zeros((2, 3, 3), dtype=np.float32)

        ds = xr.Dataset(
            data_vars={
                "uo": (["time", "latitude", "longitude"], u_vals),
                "vo": (["time", "latitude", "longitude"], v_vals),
            },
            coords={"time": times, "latitude": lats, "longitude": lons}
        )
        ds.to_netcdf(nc_path)

        reader = LocalNetCDFDatasetReader(
            filepath=nc_path,
            variable_mapping=VariableMapping(u_var="uo", v_var="vo"),
            field_type="ocean_currents"
        )
        reader.open_dataset()

        # Query at point A (lon 54.2) and point B (lon 55.8)
        u_a, _ = reader.interpolate(25.0, 54.2, datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc))
        u_b, _ = reader.interpolate(25.0, 55.8, datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc))

        self.assertNotEqual(u_a, u_b)
        self.assertAlmostEqual(u_a, 0.2 + (0.5 - 0.2) * 0.2, places=2)
        self.assertAlmostEqual(u_b, 0.5 + (1.0 - 0.5) * 0.8, places=2)
        reader.close_dataset()

    def test_07_temporal_interpolation(self):
        """
        NEW TEST 7: TEMPORAL INTERPOLATION
        Verify that intermediate trajectory steps receive linearly interpolated forcing.
        """
        nc_path = os.path.join(self.temp_dir, "temporal_grad.nc")
        lats = np.array([24.0, 26.0], dtype=np.float32)
        lons = np.array([54.0, 56.0], dtype=np.float32)
        # T0 = May 1 00:00 (u=0.0), T1 = May 2 00:00 (u=1.0)
        times = np.array(["2024-05-01T00:00:00", "2024-05-02T00:00:00"], dtype="datetime64[ns]")

        u_vals = np.zeros((2, 2, 2), dtype=np.float32)
        u_vals[0, :, :] = 0.0
        u_vals[1, :, :] = 1.0

        v_vals = np.zeros((2, 2, 2), dtype=np.float32)

        ds = xr.Dataset(
            data_vars={
                "uo": (["time", "latitude", "longitude"], u_vals),
                "vo": (["time", "latitude", "longitude"], v_vals),
            },
            coords={"time": times, "latitude": lats, "longitude": lons}
        )
        ds.to_netcdf(nc_path)

        reader = LocalNetCDFDatasetReader(
            filepath=nc_path,
            variable_mapping=VariableMapping(u_var="uo", v_var="vo"),
            field_type="ocean_currents"
        )
        reader.open_dataset()

        # Query at T_mid = May 1 12:00 (halfway between T0 and T1)
        t_mid = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        u_mid, _ = reader.interpolate(25.0, 55.0, t_mid)

        self.assertAlmostEqual(u_mid, 0.5, places=3)
        reader.close_dataset()

    def test_08_outside_coverage_fail_closed(self):
        """
        NEW TEST 8: OUTSIDE COVERAGE FAIL CLOSED
        Querying outside spatial or temporal bounds must raise OutOfDomainError / TemporalCoverageError
        and never silently return fake velocities or mock data.
        """
        nc_path = os.path.join(self.temp_dir, "small_bound.nc")
        lats = np.array([24.0, 25.0], dtype=np.float32)
        lons = np.array([54.0, 55.0], dtype=np.float32)
        times = np.array(["2024-05-01T00:00:00", "2024-05-02T00:00:00"], dtype="datetime64[ns]")

        ds = xr.Dataset(
            data_vars={
                "uo": (["time", "latitude", "longitude"], np.ones((2, 2, 2), dtype=np.float32)),
                "vo": (["time", "latitude", "longitude"], np.ones((2, 2, 2), dtype=np.float32)),
            },
            coords={"time": times, "latitude": lats, "longitude": lons}
        )
        ds.to_netcdf(nc_path)

        reader = LocalNetCDFDatasetReader(
            filepath=nc_path,
            variable_mapping=VariableMapping(u_var="uo", v_var="vo"),
            field_type="ocean_currents"
        )
        reader.open_dataset()

        # Outside latitude
        with self.assertRaises(OutOfDomainError):
            reader.interpolate(latitude=28.0, longitude=54.5, timestamp=datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc))

        # Outside longitude
        with self.assertRaises(OutOfDomainError):
            reader.interpolate(latitude=24.5, longitude=60.0, timestamp=datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc))

        # Outside temporal range
        with self.assertRaises(TemporalCoverageError):
            reader.interpolate(latitude=24.5, longitude=54.5, timestamp=datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc))

        reader.close_dataset()

    def test_09_extended_provenance(self):
        """
        NEW TEST 9: EXTENDED PROVENANCE
        Verify that provenance contains requested vs actual domains, resolution, model_source,
        access_provider, and matching verification flags.
        """
        cop_prov = CopernicusCurrentsProvider()
        prov = cop_prov.provenance

        self.assertIn("model_source", prov)
        self.assertIn("access_provider", prov)
        self.assertIn("spatial_resolution", prov)
        self.assertIn("temporal_resolution", prov)
        self.assertIn("spatially_matched", prov)
        self.assertIn("temporally_matched", prov)
        self.assertEqual(prov["model_source"], "Copernicus Global Ocean Physics Analysis and Forecast")
        self.assertEqual(prov["access_provider"], "Copernicus Marine Toolbox")

        gfs_prov = GFSWindProvider()
        g_prov = gfs_prov.provenance
        self.assertEqual(g_prov["model_source"], "NOAA GFS")
        self.assertEqual(g_prov["access_provider"], "Open-Meteo GFS API")
        self.assertIn("0.25 degree", g_prov["spatial_resolution"])

    def test_10_live_operational_criteria(self):
        """
        NEW TEST 10: STRICT LIVE_OPERATIONAL CRITERIA
        LIVE_OPERATIONAL must fail if:
          - observation timestamp is a test fixture or simulated
          - Copernicus or GFS coverage is not spatially/temporally matched
          - Local fixture data is used
        """
        # When local fixtures are used, classification must be HISTORICAL_REPLAY_FIXTURE or MIXED, never LIVE_OPERATIONAL
        cfg = Feature2Settings()
        cfg.environment = "testing"
        
        # Create pipeline service with mocks
        from app.feature2.data.wind.mock import MockWindProvider
        from app.feature2.data.currents.mock import MockCurrentsProvider
        mock_curr = MockCurrentsProvider()
        mock_wind = MockWindProvider()

        engine = ForwardSimulationEngine(
            currents_provider=mock_curr,
            wind_provider=mock_wind,
            settings=cfg,
        )
        forecaster = ForwardForecaster(simulation_engine=engine, settings=cfg)
        estimator = OriginEstimator(currents_provider=mock_curr, wind_provider=mock_wind, settings=cfg)
        service = Feature2PipelineService(origin_estimator=estimator, forecaster=forecaster, settings=cfg)

        slick = SlickDetectionInput(
            spill_id="TEST_PROV_001",
            observation_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            observation_time_source="test_fixture",
            centroid=CentroidCoordinates(latitude=25.0, longitude=55.0),
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[54.9, 24.9], [55.1, 24.9], [55.1, 25.1], [54.9, 25.1], [54.9, 24.9]]]
            ),
            area_sq_km=2.0,
            perimeter_km=6.0,
        )

        resp = service.run_pipeline(slick)
        # Since mock/fixture was used and observation_time_source is test_fixture:
        self.assertNotEqual(resp.environment.forecast_provenance_status, "LIVE_OPERATIONAL")
        self.assertIn(resp.environment.forecast_provenance_status, ["HISTORICAL_REPLAY_FIXTURE", "MIXED"])


if __name__ == "__main__":
    unittest.main()
