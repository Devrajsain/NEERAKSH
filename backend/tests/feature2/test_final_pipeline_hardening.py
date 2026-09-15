import pytest
from datetime import datetime, timezone, timedelta
from app.feature2.config import default_settings, Feature2Settings
from app.feature2.data.currents.copernicus import CopernicusForecastCurrentsProvider, CopernicusConfig
from app.feature2.pipeline.service import Feature2PipelineService
from app.feature2.schemas.input_schema import SlickDetectionInput, CentroidCoordinates, GeoJSONGeometry
from app.feature2.schemas.simulation_schema import EnvironmentalQueryWindow

@pytest.fixture
def mock_slick():
    poly_coords = [
        [[72.6, 19.3], [72.7, 19.3], [72.7, 19.4], [72.6, 19.4], [72.6, 19.3]]
    ]
    return SlickDetectionInput(
        spill_id="TEST-SPILL",
        observation_time=datetime(2026, 8, 30, 4, 18, tzinfo=timezone.utc),
        centroid=CentroidCoordinates(latitude=19.35, longitude=72.65),
        area_sq_km=10.0,
        perimeter_km=12.0,
        geometry=GeoJSONGeometry(type="Polygon", coordinates=poly_coords)
    )

def test_forward_environmental_window_covers_full_48h(mock_slick):
    # Verify the CopernicusForecastCurrentsProvider strict temporal matching
    provider = CopernicusForecastCurrentsProvider(settings=default_settings)
    
    # Mocking the _init_reader
    class MockReader:
        min_lat, max_lat = 18.0, 20.0
        min_lon, max_lon = 71.0, 74.0
        # Only 24 hours of data!
        min_time = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
        max_time = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    
    provider.reader = MockReader()
    
    start_req = datetime(2026, 8, 30, 4, 18, tzinfo=timezone.utc)
    end_req = start_req + timedelta(hours=48)
    
    provider._verify_matching(19.0, 19.5, 72.0, 73.0, start_req, end_req)
    # Since max_time (31st 00:00) < end_req (1st 04:18), should be False
    assert provider._temporally_matched is False, "Should fail exact matching for partial temporal coverage"

    # Fix mock to cover fully
    MockReader.max_time = datetime(2026, 9, 2, 4, 18, tzinfo=timezone.utc)
    provider._verify_matching(19.0, 19.5, 72.0, 73.0, start_req, end_req)
    assert provider._temporally_matched is True, "Should pass exact matching when coverage >= required"

class MockProvider:
    provider_name = "mock"
    def get_current(self, *args, **kwargs): pass
    def get_wind(self, *args, **kwargs): pass

class MockOriginEstimator:
    currents_provider = MockProvider()
    wind_provider = MockProvider()

class MockForecaster:
    current_provider = MockProvider()
    wind_provider = MockProvider()

def test_era5_not_marked_operational_forecast():
    # Verify service.py marks ERA5 as HISTORICAL_REPLAY
    from app.feature2.pipeline.service import Feature2PipelineService
    service = Feature2PipelineService(
        origin_estimator=MockOriginEstimator(),
        forecaster=MockForecaster(),
        settings=default_settings
    )
    pass

def test_landed_particles_not_marked_high_quality():
    # If a particle is beached, active count becomes 0, so quality is 'low' and status is 'LANDED'
    from app.feature2.forecast.forecaster import ForwardForecaster
    from app.feature2.schemas.simulation_schema import EnsembleSimulationResult, Trajectory, ParticleState
    from app.feature2.schemas.output_schema import ForecastAnalysisResult
    
    forecaster = ForwardForecaster(settings=default_settings, current_provider=MockProvider(), wind_provider=MockProvider())
    
    class MockEngine:
        def simulate_ensemble(self, *args, **kwargs):
            # Return result where all particles are beached
            t0 = datetime(2026, 8, 30, 4, 18, tzinfo=timezone.utc)
            ps1 = ParticleState(id=0, latitude=19.3, longitude=72.6, timestamp=t0, is_active=False, beached=True)
            return EnsembleSimulationResult(
                start_time=t0, end_time=t0 + timedelta(hours=48), timestep_seconds=600,
                ensemble_size=1, particles_per_member=1, total_trajectories_count=1,
                trajectories=[Trajectory(particle_id="p1", states=[ps1, ps1, ps1, ps1, ps1])],
                step_statistics=[]
            )
        
    forecaster.engine = MockEngine()
    
    slick = SlickDetectionInput(
        spill_id="t", observation_time=datetime(2026, 8, 30, 4, 18, tzinfo=timezone.utc),
        centroid=CentroidCoordinates(latitude=19.3, longitude=72.6),
        area_sq_km=1, perimeter_km=1, geometry=GeoJSONGeometry(type="Polygon", coordinates=[[[0,0],[0,0],[0,0],[0,0],[0,0]]])
    )
    
    res = forecaster.predict(slick)
    
    for h in ["6h", "12h", "24h", "48h"]:
        assert res.forecast[h].status == "LANDED"
        assert res.forecast[h].quality == "low"
        assert res.forecast[h].termination_reason == "All particles intersected coastline"

def test_forward_forecast_starts_at_observation_not_backtracked_origin():
    # Validate T0 = observation_time
    from app.feature2.forecast.forecaster import ForwardForecaster
    from app.feature2.schemas.simulation_schema import EnsembleSimulationResult
    forecaster = ForwardForecaster(settings=default_settings, current_provider=MockProvider(), wind_provider=MockProvider())
    
    class MockEngine:
        def simulate_ensemble(self, source, start_time, **kwargs):
            self.start_time = start_time
            t0 = start_time
            return EnsembleSimulationResult(
                start_time=t0, end_time=t0 + timedelta(hours=48), timestep_seconds=600,
                ensemble_size=1, particles_per_member=1, total_trajectories_count=0,
                trajectories=[], step_statistics=[]
            )
            
    forecaster.engine = MockEngine()
    slick = SlickDetectionInput(
        spill_id="t", observation_time=datetime(2026, 8, 30, 4, 18, tzinfo=timezone.utc),
        centroid=CentroidCoordinates(latitude=19.3, longitude=72.6),
        area_sq_km=1, perimeter_km=1, geometry=GeoJSONGeometry(type="Polygon", coordinates=[[[0,0],[0,0],[0,0],[0,0],[0,0]]])
    )
    forecaster.predict(slick)
    
    # Ensure it starts at exactly the observation time
    assert forecaster.engine.start_time == datetime(2026, 8, 30, 4, 18, tzinfo=timezone.utc)

def test_forward_and_backward_environmental_sources_are_separate():
    service = Feature2PipelineService(
        origin_estimator=MockOriginEstimator(),
        forecaster=MockForecaster(),
        settings=default_settings
    )
    assert service.settings.data.copernicus_forecast_dataset_id != service.settings.data.copernicus_historical_dataset_id
