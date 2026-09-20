"""
Tests for Phase 3C: OpenOil Forward Ensemble logic.
"""

import os
import unittest
from datetime import datetime, timezone, timedelta
import tempfile
import numpy as np

import pytest

from app.bayesian.schemas import (
    BayesianCandidateHypothesis,
    OpenOilEnsembleConfig
)
from app.bayesian.openoil_runner import OpenOilSimulationRunner
from app.feature2.data.wind.era5 import ERA5WindProvider, ERA5Config
from app.feature2.data.currents.copernicus import CopernicusForecastCurrentsProvider, CopernicusConfig
from app.feature2.data.cache import EnvironmentalDataCacheManager

# Test if opendrift is actually available for integration tests
try:
    from opendrift.readers import reader_constant
    import opendrift
    OPENDRIFT_AVAILABLE = True
except ImportError:
    OPENDRIFT_AVAILABLE = False


class MockProvider:
    def __init__(self, success: bool, filepath: str = None, name: str = "mock_provider"):
        self.success = success
        self._active_filepath = filepath
        self.provider_name = name
        self.mock_reader = None

    @property
    def active_filepath(self):
        return self._active_filepath

    def fetch_grid(self, window):
        if not self.success:
            return False
        return True


class TestOpenOilSimulationRunner(unittest.TestCase):
    
    def setUp(self):
        from app.feature3.schemas import AISRecord
        
        obs_time1 = datetime(2018, 8, 3, 10, 0, 0, tzinfo=timezone.utc)
        obs_time2 = datetime(2018, 8, 3, 10, 15, 0, tzinfo=timezone.utc)
        
        obs1 = AISRecord(mmsi="123456789", timestamp=obs_time1, latitude=55.25, longitude=4.0)
        obs2 = AISRecord(mmsi="123456789", timestamp=obs_time2, latitude=55.30, longitude=4.1)

        self.candidate = BayesianCandidateHypothesis(
            candidate_id="123456789",
            mmsi="123456789",
            release_position={"latitude": 55.25, "longitude": 4.0},
            release_time=obs_time1,
            prior_probability=1.0,
            observations=[obs1, obs2]
        )
        self.obs_time = datetime(2018, 8, 3, 12, 0, 0, tzinfo=timezone.utc)
        self.config = OpenOilEnsembleConfig(
            ensemble_size=5,
            time_step_seconds=900,
            time_step_output_seconds=3600,
            release_radius_m=500.0,
            environment_margin_deg=1.5,
            oil_type="Generic Diesel",
            random_seed=42
        )

    def test_validation_error_on_invalid_timestamp(self):
        wind = MockProvider(True)
        curr = MockProvider(True)
        runner = OpenOilSimulationRunner(wind_provider=wind, currents_provider=curr, config=self.config)
        
        invalid_obs = self.candidate.release_time - timedelta(hours=1)
        res = runner.run_candidate(self.candidate, invalid_obs)
        
        self.assertEqual(res.status, "VALIDATION_ERROR")
        self.assertIn("strictly before", res.error_message)

    def test_environmental_incomplete_on_provider_failure(self):
        wind = MockProvider(False) # Fails
        curr = MockProvider(True)
        runner = OpenOilSimulationRunner(wind_provider=wind, currents_provider=curr, config=self.config)
        
        res = runner.run_candidate(self.candidate, self.obs_time)
        self.assertEqual(res.status, "ENVIRONMENTAL_DATA_INCOMPLETE")

    @pytest.mark.skipif(not OPENDRIFT_AVAILABLE, reason="OpenDrift not installed")
    def test_tiny_openoil_with_reader_constant(self):
        wind = MockProvider(True, name="mock_wind")
        wind.mock_reader = reader_constant.Reader({'x_wind': 5.0, 'y_wind': 0.0})
        
        curr = MockProvider(True, name="mock_curr")
        curr.mock_reader = reader_constant.Reader({'x_sea_water_velocity': 0.5, 'y_sea_water_velocity': 0.0})
        
        runner = OpenOilSimulationRunner(wind_provider=wind, currents_provider=curr, config=self.config)
        res = runner.run_candidate(self.candidate, self.obs_time)
        
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.ensemble_size_requested, 5)
        self.assertEqual(res.ensemble_size_returned, 5)
        self.assertEqual(res.active_particle_count, 5)
        self.assertEqual(res.stranded_particle_count, 0)
        self.assertEqual(len(res.final_particle_states), 5)
        
        # We expect mass_oil to be available in OpenOil
        self.assertIsNotNone(res.final_particle_states[0].mass_oil_kg)
        self.assertIsNotNone(res.weathering_summary.mean_mass_oil_kg)

    @pytest.mark.skipif(not OPENDRIFT_AVAILABLE, reason="OpenDrift not installed")
    def test_real_era5_cmems_integration(self):
        """
        Integration test verifying OpenDrift generic NetCDF reader works directly with
        actual cached files from Feature 2.
        """
        # Find a real ERA5 cache file to test against
        cache_dir = os.path.join(os.getcwd(), "data_cache")
        if not os.path.exists(cache_dir):
            pytest.skip("No data_cache directory available.")
            
        import glob
        era5_files = glob.glob(os.path.join(cache_dir, "era5/**/*.nc"), recursive=True)
        cmems_files = glob.glob(os.path.join(cache_dir, "copernicus/**/*.nc"), recursive=True)
        
        if not era5_files:
            era5_files = glob.glob(os.path.join(cache_dir, "era5*.nc"), recursive=True)
        if not cmems_files:
            cmems_files = glob.glob(os.path.join(cache_dir, "copernicus*.nc"), recursive=True)
        if not era5_files and not cmems_files:
            era5_files = [f for f in glob.glob(os.path.join(cache_dir, "**/*.nc"), recursive=True) if 'era5' in f]
            cmems_files = [f for f in glob.glob(os.path.join(cache_dir, "**/*.nc"), recursive=True) if 'copernicus' in f]
            
        if not era5_files or not cmems_files:
            pytest.skip("No real ERA5 or CMEMS NetCDF cached files found for integration test.")
            
        era5_file = era5_files[0]
        cmems_file = cmems_files[0]
        
        # Quick parse to find valid timestamp to test against
        from opendrift.readers import reader_netCDF_CF_generic
        wind_r = reader_netCDF_CF_generic.Reader(era5_file)
        
        start_t = wind_r.start_time
        obs_t = start_t + timedelta(hours=2)
        if obs_t > wind_r.end_time:
            obs_t = wind_r.end_time
            
        from app.feature3.schemas import AISRecord
        obs_real = AISRecord(
            mmsi="123", 
            timestamp=start_t, 
            latitude=float(wind_r.ymin + (wind_r.ymax - wind_r.ymin)/2), 
            longitude=float(wind_r.xmin + (wind_r.xmax - wind_r.xmin)/2)
        )
        
        candidate = BayesianCandidateHypothesis(
            candidate_id="123",
            mmsi="123",
            release_position={"latitude": obs_real.latitude, "longitude": obs_real.longitude},
            release_time=start_t,
            prior_probability=1.0,
            observations=[obs_real]
        )
        
        # Use mocked providers that just pass the real file
        wind = MockProvider(True, filepath=era5_file, name="era5_test")
        curr = MockProvider(True, filepath=cmems_file, name="cmems_test")
        
        config = OpenOilEnsembleConfig(
            ensemble_size=3,
            time_step_seconds=1800,
            time_step_output_seconds=3600,
            release_radius_m=100.0,
            environment_margin_deg=0.5
        )
        
        runner = OpenOilSimulationRunner(wind_provider=wind, currents_provider=curr, config=config)
        res = runner.run_candidate(candidate, obs_t)
        
        if res.status != "SUCCESS":
            # Sometimes environmental coverage fails if coordinates don't perfectly overlap
            if "OPENDRIFT_SIMULATION_ERROR" in res.status and ("No data available" in res.error_message or "Missing variables" in res.error_message):
                pytest.skip(f"Could not run simulation because cached grids don't overlap properly: {res.error_message}")
            self.fail(f"Real integration failed: {res.status} - {res.error_message}")
            
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.ensemble_size_returned, 3)
        self.assertTrue(len(res.final_particle_states) == 3)
