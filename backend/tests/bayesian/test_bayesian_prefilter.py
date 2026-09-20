import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.bayesian.prefilter import BayesianBackwardPrefilter
from app.bayesian.schemas import BayesianPrefilterResult
from app.feature2.data.currents.mock import MockCurrentsProvider
from app.feature2.data.wind.mock import MockWindProvider
from app.feature2.schemas.input_schema import SlickDetectionInput, CentroidCoordinates


@pytest.fixture
def slick_input() -> SlickDetectionInput:
    return SlickDetectionInput(
        spill_id="bayesian_test_01",
        observation_time=datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc),
        centroid=CentroidCoordinates(latitude=45.0, longitude=-30.0),
        geometry={
            "type": "Polygon",
            "coordinates": [[
                [-30.1, 44.9], [-29.9, 44.9], [-29.9, 45.1], [-30.1, 45.1], [-30.1, 44.9]
            ]]
        },
        area_sq_km=10.0,
        perimeter_km=12.0
    )


@pytest.fixture
def prefilter() -> BayesianBackwardPrefilter:
    # Use mock providers for deterministic, fast tests
    currents = MockCurrentsProvider(const_u=0.5, const_v=0.0)
    wind = MockWindProvider(pattern="uniform", const_u=5.0, const_v=0.0)
    return BayesianBackwardPrefilter(currents_provider=currents, wind_provider=wind)


def test_default_horizon(prefilter: BayesianBackwardPrefilter, slick_input: SlickDetectionInput):
    """Test 1: default horizon = 12h"""
    # Assuming config defaults to 12.0
    result = prefilter.run_prefilter(source=slick_input)
    assert result.backward_horizon_hours == 12.0
    assert (result.observation_time - result.prefilter_start_time).total_seconds() == 12.0 * 3600.0


def test_custom_valid_horizon(prefilter: BayesianBackwardPrefilter, slick_input: SlickDetectionInput):
    """Test 2: custom valid horizon: 6h, 12h, 24h"""
    for h in [6.0, 12.0, 24.0]:
        result = prefilter.run_prefilter(source=slick_input, backward_horizon_hours=h)
        assert result.backward_horizon_hours == h
        assert (result.observation_time - result.prefilter_start_time).total_seconds() == h * 3600.0


def test_invalid_horizon(prefilter: BayesianBackwardPrefilter, slick_input: SlickDetectionInput):
    """Test 3: invalid horizon: <6h, >24h"""
    with pytest.raises(ValueError):
        prefilter.run_prefilter(source=slick_input, backward_horizon_hours=5.0)
        
    with pytest.raises(ValueError):
        prefilter.run_prefilter(source=slick_input, backward_horizon_hours=25.0)


def test_role_is_prefilter_only(prefilter: BayesianBackwardPrefilter, slick_input: SlickDetectionInput):
    """Test 4: result contains role == 'SEARCH_PREFILTER_ONLY'"""
    result = prefilter.run_prefilter(source=slick_input, backward_horizon_hours=12.0)
    assert result.role == "SEARCH_PREFILTER_ONLY"


def test_spatial_search_region(prefilter: BayesianBackwardPrefilter, slick_input: SlickDetectionInput):
    """Test 5: result contains a spatial search region."""
    result = prefilter.run_prefilter(source=slick_input, backward_horizon_hours=12.0)
    assert isinstance(result.candidate_spatial_region, dict)
    assert result.candidate_spatial_region["type"] == "Feature"
    assert result.candidate_spatial_region["geometry"]["type"] == "Polygon"
    assert len(result.candidate_spatial_region["geometry"]["coordinates"][0]) == 5 # 4 corners + closed ring


def test_temporal_search_window(prefilter: BayesianBackwardPrefilter, slick_input: SlickDetectionInput):
    """Test 6: result contains a temporal search window."""
    result = prefilter.run_prefilter(source=slick_input, backward_horizon_hours=12.0)
    assert hasattr(result, "prefilter_start_time")
    assert hasattr(result, "prefilter_end_time")
    assert result.prefilter_start_time < result.prefilter_end_time


def test_timestamps_utc_aware(prefilter: BayesianBackwardPrefilter, slick_input: SlickDetectionInput):
    """Test 7: timestamps are UTC-aware."""
    result = prefilter.run_prefilter(source=slick_input, backward_horizon_hours=12.0)
    assert result.observation_time.tzinfo == timezone.utc
    assert result.prefilter_start_time.tzinfo == timezone.utc
    assert result.prefilter_end_time.tzinfo == timezone.utc
