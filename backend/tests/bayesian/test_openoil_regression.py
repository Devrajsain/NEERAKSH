import pytest
from datetime import datetime, timezone
from pydantic import BaseModel
import numpy as np

from app.bayesian.schemas import BayesianCandidateHypothesis, OpenOilEnsembleConfig
from app.bayesian.openoil_runner import OpenOilSimulationRunner

class MockOpendrift:
    class readers:
        class reader_netCDF_CF_generic:
            class Reader:
                def __init__(self, *args, **kwargs):
                    pass
    class models:
        class openoil:
            class OpenOil:
                pass

class MockOpenOilInstance:
    def __init__(self, loglevel=50):
        self.history = {
            'lon': np.array([[2.5, 2.5]]),
            'lat': np.array([[41.4, 41.4]]),
            'status': np.array([[0, 0]]),
            'mass_oil': np.array([[1000, 1000]]),
        }
    def get_property(self, name):
        return [self.history.get(name, None)]
    def add_reader(self, *args, **kwargs):
        pass
    def seed_elements(self, *args, **kwargs):
        pass
    def run(self, *args, **kwargs):
        pass

@pytest.fixture
def mock_opendrift(monkeypatch):
    import app.bayesian.openoil_runner as orunner
    monkeypatch.setattr(orunner, "OpenOil", MockOpenOilInstance)
    monkeypatch.setattr(orunner, "opendrift", MockOpendrift)

class MockProvider:
    @property
    def mock_reader(self):
        return MockOpendrift.readers.reader_netCDF_CF_generic.Reader()
    def fetch_grid(self, env_window):
        return True
    @property
    def active_filepath(self):
        return None
    @property
    def provider_name(self):
        return "mock"

def test_run_candidate_random_seed_none(mock_opendrift):
    config = OpenOilEnsembleConfig(random_seed=None)
    runner = OpenOilSimulationRunner(MockProvider(), MockProvider(), config=config)
    
    candidate = BayesianCandidateHypothesis(
        candidate_id="TEST_1", mmsi="111", 
        release_position={"latitude": 41.4, "longitude": 2.5},
        release_time=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
        prior_probability=0.2,
        observations=[
            {'mmsi': '111', 'latitude': 41.4, 'longitude': 2.5, 'timestamp': datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)}
        ]
    )
    
    result = runner.run_candidate(
        candidate, 
        observation_time=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
    )
    
    assert result.status == "SUCCESS"

def test_run_candidate_random_seed_provided(mock_opendrift):
    config = OpenOilEnsembleConfig(random_seed=42)
    runner = OpenOilSimulationRunner(MockProvider(), MockProvider(), config=config)
    
    candidate = BayesianCandidateHypothesis(
        candidate_id="TEST_2", mmsi="222", 
        release_position={"latitude": 41.4, "longitude": 2.5},
        release_time=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
        prior_probability=0.2,
        observations=[
            {'mmsi': '222', 'latitude': 41.4, 'longitude': 2.5, 'timestamp': datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)}
        ]
    )
    
    result = runner.run_candidate(
        candidate, 
        observation_time=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
    )
    
    assert result.status == "SUCCESS"
