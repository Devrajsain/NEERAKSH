import pytest
import math
from datetime import datetime, timezone, timedelta
from shapely.geometry import Polygon

from app.bayesian.config import LikelihoodConfig
from app.bayesian.schemas import (
    OpenOilSimulationResult,
    ParticleState,
    CandidateLikelihood
)
from app.feature2.schemas.input_schema import SlickDetectionInput, CentroidCoordinates, GeoJSONGeometry
from app.bayesian.likelihood import LikelihoodEngine
from app.feature2.geo.coordinates import haversine_distance_km

def _create_obs(spill_id="obs1", lat=0.0, lon=0.0, time=None, coords=None):
    if time is None:
        time = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    if coords is None:
        coords = [[[lon-1, lat-1], [lon+1, lat-1], [lon+1, lat+1], [lon-1, lat+1], [lon-1, lat-1]]]
    
    return SlickDetectionInput(
        spill_id=spill_id,
        observation_time=time,
        area_sq_km=10.0,
        perimeter_km=10.0,
        centroid=CentroidCoordinates(latitude=lat, longitude=lon),
        geometry=GeoJSONGeometry(type="Polygon", coordinates=coords)
    )

def _create_sim(particles, actual_time=None, req_time=None):
    if actual_time is None:
        actual_time = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    if req_time is None:
        req_time = actual_time
        
    return OpenOilSimulationResult(
        candidate_id="c1",
        mmsi="123456789",
        status="SUCCESS",
        release_timestamp=actual_time - timedelta(hours=1),
        requested_observation_timestamp=req_time,
        actual_final_timestamp=actual_time,
        final_time_offset_seconds=0.0,
        ensemble_size_requested=len(particles),
        ensemble_size_returned=len(particles),
        active_particle_count=len([p for p in particles if p.status == "active"]),
        stranded_particle_count=len([p for p in particles if p.status == "stranded"]),
        other_terminal_particle_count=len([p for p in particles if p.status not in ("active", "stranded")]),
        final_particle_states=particles
    )

def test_threshold_all_inside():
    # A1. All particles inside polygon
    obs = _create_obs(lon=0, lat=0, coords=[[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]])
    particles = [
        ParticleState(longitude=0, latitude=0, status="active", original_status_code=0),
        ParticleState(longitude=0.5, latitude=0.5, status="active", original_status_code=0)
    ]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 1.0
    assert result.log_likelihood == 0.0

def test_threshold_none_inside():
    # A2. No particles inside polygon
    obs = _create_obs(lon=0, lat=0, coords=[[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]])
    particles = [
        ParticleState(longitude=2, latitude=2, status="active", original_status_code=0)
    ]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 0.0
    assert result.log_likelihood == float('-inf')

def test_threshold_some_inside():
    # A3. Some particles inside
    obs = _create_obs(lon=0, lat=0, coords=[[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]])
    particles = [
        ParticleState(longitude=0, latitude=0, status="active", original_status_code=0),
        ParticleState(longitude=2, latitude=2, status="active", original_status_code=0)
    ]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 0.5
    assert result.log_likelihood == math.log(0.5)

def test_threshold_on_boundary():
    # A4. Particle exactly on polygon boundary -> MUST count as compatible
    obs = _create_obs(lon=0, lat=0, coords=[[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]])
    particles = [
        ParticleState(longitude=1.0, latitude=1.0, status="active", original_status_code=0)
    ]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 1.0

def test_invalid_particle_coordinates():
    # A5. Invalid particle coordinates
    obs = _create_obs(lon=0, lat=0, coords=[[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]])
    particles = [
        ParticleState(longitude=float('nan'), latitude=float('nan'), status="active", original_status_code=0)
    ]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 0.0
    assert result.per_observation_diagnostics[0].error_message == "No valid particles available for spatial likelihood evaluation."

def test_zero_valid_particles():
    # A6. Zero valid particles
    obs = _create_obs()
    sim = _create_sim([])
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 0.0
    assert result.log_likelihood == float('-inf')
    assert "No valid particles" in result.per_observation_diagnostics[0].error_message

def test_gaussian_known_distance_sigma():
    # B7. Known distance + known sigma
    obs = _create_obs(lat=10.0, lon=10.0)
    # create particle at 10.01, 10.0
    p_lat = 10.01
    p_lon = 10.0
    particles = [ParticleState(longitude=p_lon, latitude=p_lat, status="active", original_status_code=0)]
    sim = _create_sim(particles)
    
    r_km = haversine_distance_km(p_lat, p_lon, 10.0, 10.0)
    r_m = r_km * 1000.0
    sigma_m = 500.0
    
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="gaussian", gaussian_sigma_m=sigma_m))
    result = engine.evaluate([obs], sim)
    
    expected_L = (1.0 / (2.0 * math.pi * sigma_m**2)) * math.exp(- (r_m**2) / (2.0 * sigma_m**2))
    assert math.isclose(result.likelihood, expected_L, rel_tol=1e-5)

def test_gaussian_sigma_validation():
    # B8. sigma <= 0 validation
    from pydantic import ValidationError
    obs = _create_obs()
    particles = [ParticleState(longitude=0, latitude=0, status="active", original_status_code=0)]
    sim = _create_sim(particles)
    with pytest.raises(ValidationError):
        engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="gaussian", gaussian_sigma_m=0.0))

def test_gaussian_multiple_particles_mean_aggregation():
    # B9 & B10. Multiple particles & Ensemble mean aggregation
    obs = _create_obs(lat=0.0, lon=0.0)
    particles = [
        ParticleState(longitude=0, latitude=0, status="active", original_status_code=0),
        ParticleState(longitude=0.01, latitude=0, status="active", original_status_code=0)
    ]
    sim = _create_sim(particles)
    sigma_m = 1000.0
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="gaussian", gaussian_sigma_m=sigma_m))
    result = engine.evaluate([obs], sim)
    
    # particle 1: r=0 -> L1 = 1 / (2*pi*sigma^2)
    # particle 2: r_km = haversine(0, 0, 0, 0.01) -> L2 = 1 / (2*pi*sigma^2) * exp(-r^2 / 2*sigma^2)
    L1 = (1.0 / (2.0 * math.pi * sigma_m**2))
    r_m = haversine_distance_km(0.0, 0.01, 0.0, 0.0) * 1000.0
    L2 = L1 * math.exp(- (r_m**2) / (2.0 * sigma_m**2))
    
    expected_L = (L1 + L2) / 2.0
    assert math.isclose(result.likelihood, expected_L, rel_tol=1e-5)

def test_gaussian_numerical_stability():
    # B11. Numerical stability / very small likelihood
    obs = _create_obs(lat=0.0, lon=0.0)
    # particle extremely far away
    particles = [ParticleState(longitude=90.0, latitude=90.0, status="active", original_status_code=0)]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="gaussian", gaussian_sigma_m=10.0))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 0.0
    assert result.log_likelihood == float('-inf')

def test_timing_exact_match():
    # C12. Exact timestamp match
    t = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    obs = _create_obs(time=t)
    particles = [ParticleState(longitude=0, latitude=0, status="active", original_status_code=0)]
    sim = _create_sim(particles, actual_time=t)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.per_observation_diagnostics[0].temporal_compatible is True

def test_timing_within_tolerance():
    # C13. Timestamp within tolerance
    t = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    obs = _create_obs(time=t)
    particles = [ParticleState(longitude=0, latitude=0, status="active", original_status_code=0)]
    sim = _create_sim(particles, actual_time=t + timedelta(minutes=30))
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold", observation_time_tolerance_seconds=3600))
    result = engine.evaluate([obs], sim)
    assert result.per_observation_diagnostics[0].temporal_compatible is True

def test_timing_outside_tolerance():
    # C14. Timestamp outside tolerance
    t = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    obs = _create_obs(time=t)
    particles = [ParticleState(longitude=0, latitude=0, status="active", original_status_code=0)]
    sim = _create_sim(particles, actual_time=t + timedelta(hours=2))
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold", observation_time_tolerance_seconds=3600))
    result = engine.evaluate([obs], sim)
    assert result.likelihood == 0.0
    assert result.per_observation_diagnostics[0].temporal_compatible is False
    assert "Temporal incompatibility" in result.per_observation_diagnostics[0].error_message

def test_timezone_aware_utc_handling():
    # C15. timezone-aware UTC handling
    t_utc = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    # tz offset of +2 hours
    t_other = datetime(2026, 9, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    obs = _create_obs(time=t_utc)
    particles = [ParticleState(longitude=0, latitude=0, status="active", original_status_code=0)]
    sim = _create_sim(particles, actual_time=t_other) # These should represent the exact same time
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.per_observation_diagnostics[0].temporal_compatible is True

def test_multiple_observations():
    # D16, D17, D18. Multiple observations
    obs1 = _create_obs(spill_id="1", lon=0, lat=0)
    obs2 = _create_obs(spill_id="2", lon=0, lat=0) # Same exact observation essentially
    
    particles = [
        ParticleState(longitude=0, latitude=0, status="active", original_status_code=0),
        ParticleState(longitude=2, latitude=2, status="active", original_status_code=0)
    ]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs1, obs2], sim)
    
    assert result.observation_count == 2
    # L1 = 0.5, L2 = 0.5 -> L_joint = 0.25
    assert math.isclose(result.likelihood, 0.25, rel_tol=1e-5)
    # log_L_joint = log(0.5) + log(0.5) = 2 * log(0.5)
    assert math.isclose(result.log_likelihood, 2 * math.log(0.5), rel_tol=1e-5)

def test_status_handling():
    # E19, E20, E21. Status handling
    obs = _create_obs(lon=0, lat=0)
    particles = [
        ParticleState(longitude=0, latitude=0, status="active", original_status_code=0),
        ParticleState(longitude=0, latitude=0, status="stranded", original_status_code=1),
        ParticleState(longitude=0, latitude=0, status="evaporated", original_status_code=2)
    ]
    sim = _create_sim(particles)
    
    # default: include_stranded=False, include_other=False
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    assert result.per_observation_diagnostics[0].total_particles == 3
    assert result.per_observation_diagnostics[0].active_particles == 1
    assert result.per_observation_diagnostics[0].stranded_particles == 1
    assert result.per_observation_diagnostics[0].other_terminal_particles == 1
    assert result.per_observation_diagnostics[0].valid_particles_used == 1
    assert result.per_observation_diagnostics[0].excluded_status_particles == 2
    
    # include_stranded=True
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold", include_stranded_particles=True))
    result = engine.evaluate([obs], sim)
    assert result.per_observation_diagnostics[0].valid_particles_used == 2
    assert result.per_observation_diagnostics[0].excluded_status_particles == 1

def test_architecture_no_phase5_fields():
    # F22, F23, F24, F25. No phase 5 fields
    obs = _create_obs()
    particles = [ParticleState(longitude=0, latitude=0, status="active", original_status_code=0)]
    sim = _create_sim(particles)
    engine = LikelihoodEngine(LikelihoodConfig(likelihood_mode="threshold"))
    result = engine.evaluate([obs], sim)
    
    # Ensure it's a CandidateLikelihood and has no posterior fields
    assert isinstance(result, CandidateLikelihood)
    assert not hasattr(result, "posterior_probability")
    assert not hasattr(result, "rank")
    assert not hasattr(result, "confidence")
