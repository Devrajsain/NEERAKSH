import pytest
import math
from datetime import datetime, timezone

from app.bayesian.schemas import (
    BayesianPosteriorResult,
    CandidatePosterior,
    CandidateGenerationResult,
    BayesianCandidateHypothesis,
    OpenOilSimulationResult,
    CandidateLikelihood,
    ObservationLikelihoodDiagnostics
)
from app.feature2.schemas.simulation_schema import EnsembleStepStatistics
from app.bayesian.confidence import PhysicsAwareConfidenceEngine

def _create_base_posterior(candidate_id: str, prob: float) -> CandidatePosterior:
    return CandidatePosterior(
        candidate_id=candidate_id,
        mmsi="123",
        release_latitude=0.0,
        release_longitude=0.0,
        release_timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc),
        prior=0.5,
        likelihood=0.5,
        log_likelihood=-1.0,
        unnormalized_log_weight=-2.0,
        posterior_probability=prob,
        likelihood_mode="gaussian",
        evaluation_status="SUCCESS"
    )

def _create_base_metadata(truncated: bool = False) -> BayesianPosteriorResult:
    return BayesianPosteriorResult(
        status="SUCCESS",
        hypothesis_space_truncated=truncated,
        candidate_limit=10,
        total_valid_candidates=20 if truncated else 2,
        returned_candidate_count=2,
        prior_mode="UNIFORM",
        evaluated_candidate_count=2,
        positive_likelihood_candidate_count=2,
        normalization_constant=1.0,
        log_normalization_constant=0.0,
        posterior_sum=1.0,
        posteriors=[_create_base_posterior("c0", 0.7), _create_base_posterior("c1", 0.3)]
    )

def _create_sim(candidate_id: str, requested: int, active: int, stranded: int) -> OpenOilSimulationResult:
    return OpenOilSimulationResult(
        candidate_id=candidate_id,
        mmsi="123",
        status="SUCCESS",
        release_timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc),
        requested_observation_timestamp=datetime(2026, 9, 2, tzinfo=timezone.utc),
        ensemble_size_requested=requested,
        active_particle_count=active,
        stranded_particle_count=stranded
    )

def _create_lh(candidate_id: str, temp_compat: bool) -> CandidateLikelihood:
    return CandidateLikelihood(
        candidate_id=candidate_id,
        likelihood_mode="gaussian",
        likelihood=0.5,
        log_likelihood=-1.0,
        observation_count=1,
        per_observation_diagnostics=[
            ObservationLikelihoodDiagnostics(
                spill_id="s1",
                observation_time=datetime(2026, 9, 2, tzinfo=timezone.utc),
                observation_time_tolerance_seconds=1800,
                temporal_compatible=temp_compat,
                total_particles=50,
                active_particles=50,
                stranded_particles=0,
                other_terminal_particles=0,
                valid_particles_used=50,
                excluded_status_particles=0,
                likelihood=0.5,
                log_likelihood=-1.0,
                final_time_offset_seconds=0.0 if temp_compat else 2000.0
            )
        ]
    )

def _create_stats(spread: float) -> EnsembleStepStatistics:
    return EnsembleStepStatistics(
        timestamp=datetime(2026, 9, 2, tzinfo=timezone.utc),
        active_particle_count=50,
        mean_latitude=0.0,
        mean_longitude=0.0,
        variance_east_m2=0.0,
        variance_north_m2=0.0,
        covariance_en_m2=0.0,
        covariance_matrix_m2=[[0.0, 0.0], [0.0, 0.0]],
        spread_radius_m=spread
    )

def _run_engine(sims=None, lhs=None, stats_map=None, truncated=False):
    engine = PhysicsAwareConfidenceEngine()
    post_meta = _create_base_metadata(truncated=truncated)
    cg_res = CandidateGenerationResult(candidate_count=2, total_valid_candidates=2, prior_candidate_count=2, candidates=[])
    if sims is None: sims = []
    if lhs is None: lhs = []
    if stats_map is None: stats_map = {}
    return engine.compute_confidence(post_meta, cg_res, sims, lhs, stats_map)

# Tests

def test_1_high_ensemble_retention():
    sim = _create_sim("c0", 50, 48, 0)
    conf = _run_engine(sims=[sim])[0]
    flag = next(f for f in conf.flags if f.flag_name == "LOW_ENSEMBLE_RETENTION")
    assert not flag.triggered

def test_2_low_ensemble_retention():
    sim = _create_sim("c0", 50, 20, 0) # < 0.5
    conf = _run_engine(sims=[sim])[0]
    flag = next(f for f in conf.flags if f.flag_name == "LOW_ENSEMBLE_RETENTION")
    assert flag.triggered

def test_3_zero_requested_ensemble():
    sim = _create_sim("c0", 0, 0, 0)
    conf = _run_engine(sims=[sim])[0]
    diag = next(d for d in conf.diagnostics if d.metric_name == "ensemble_retention_fraction")
    assert diag.status == "UNAVAILABLE"

def test_4_strong_coastline_interaction():
    sim = _create_sim("c0", 50, 30, 15) # 30% stranded > 20%
    conf = _run_engine(sims=[sim])[0]
    flag = next(f for f in conf.flags if f.flag_name == "STRONG_COASTLINE_INTERACTION")
    assert flag.triggered

def test_5_no_coastline_interaction():
    sim = _create_sim("c0", 50, 48, 0)
    conf = _run_engine(sims=[sim])[0]
    flag = next(f for f in conf.flags if f.flag_name == "STRONG_COASTLINE_INTERACTION")
    assert not flag.triggered

def test_6_temporal_mismatch():
    lh = _create_lh("c0", temp_compat=False)
    conf = _run_engine(lhs=[lh])[0]
    flag = next(f for f in conf.flags if f.flag_name == "TEMPORAL_MISMATCH")
    assert flag.triggered

def test_7_temporal_compatibility():
    lh = _create_lh("c0", temp_compat=True)
    conf = _run_engine(lhs=[lh])[0]
    flag = next(f for f in conf.flags if f.flag_name == "TEMPORAL_MISMATCH")
    assert not flag.triggered

def test_8_high_spatial_dispersion():
    stats = _create_stats(5500.0) # > 5000
    conf = _run_engine(stats_map={"c0": stats})[0]
    flag = next(f for f in conf.flags if f.flag_name == "HIGH_SPATIAL_DISPERSION")
    assert flag.triggered

def test_9_low_spatial_dispersion():
    stats = _create_stats(1000.0)
    conf = _run_engine(stats_map={"c0": stats})[0]
    flag = next(f for f in conf.flags if f.flag_name == "HIGH_SPATIAL_DISPERSION")
    assert not flag.triggered

def test_10_truncated_hypothesis_space():
    conf = _run_engine(truncated=True)[0]
    flag = next(f for f in conf.flags if f.flag_name == "HYPOTHESIS_SPACE_TRUNCATED")
    assert flag.triggered
    assert conf.hypothesis_space_truncated

def test_11_12_13_missing_metrics():
    conf = _run_engine()[0]
    assert next(d for d in conf.diagnostics if d.metric_name == "weathering_sensitivity").status == "UNAVAILABLE"
    assert next(d for d in conf.diagnostics if d.metric_name == "ais_temporal_uncertainty").status == "UNAVAILABLE"
    assert next(d for d in conf.diagnostics if d.metric_name == "environmental_data_completeness").status == "UNAVAILABLE"

def test_14_posterior_immutability():
    # Prove input posterior == output posterior
    engine = PhysicsAwareConfidenceEngine()
    post_meta = _create_base_metadata()
    cg_res = CandidateGenerationResult(candidate_count=2, total_valid_candidates=2, prior_candidate_count=2, candidates=[])
    
    # Run with lots of bad flags
    sim = _create_sim("c0", 50, 10, 30) # bad retention, bad stranded
    lh = _create_lh("c0", False) # bad time
    stats = _create_stats(9000.0) # bad spread
    
    results = engine.compute_confidence(post_meta, cg_res, [sim], [lh], {"c0": stats})
    
    # Posterior for c0 in input was 0.7
    assert math.isclose(results[0].posterior_probability, 0.7)
    # Posterior for c1 in input was 0.3
    assert math.isclose(results[1].posterior_probability, 0.3)

def test_15_confidence_remains_indeterminate():
    conf = _run_engine()[0]
    assert conf.confidence_level == "INDETERMINATE"

def test_16_uncalibrated_threshold_metadata():
    sim = _create_sim("c0", 50, 10, 30)
    conf = _run_engine(sims=[sim])[0]
    ret_flag = next(f for f in conf.flags if f.flag_name == "LOW_ENSEMBLE_RETENTION")
    assert ret_flag.threshold_status == "THRESHOLD_REQUIRES_CALIBRATION"
    coast_flag = next(f for f in conf.flags if f.flag_name == "STRONG_COASTLINE_INTERACTION")
    assert coast_flag.threshold_status == "THRESHOLD_REQUIRES_CALIBRATION"
    
    lh = _create_lh("c0", temp_compat=False)
    conf_time = _run_engine(lhs=[lh])[0]
    time_flag = next(f for f in conf_time.flags if f.flag_name == "TEMPORAL_MISMATCH")
    # Temporal mismatch is an ESTABLISHED hard boundary, not a calibration threshold
    assert time_flag.threshold_status == "ESTABLISHED"

def test_17_candidate_specific_diagnostics():
    sim_0 = _create_sim("c0", 50, 48, 0)
    sim_1 = _create_sim("c1", 50, 10, 0)
    results = _run_engine(sims=[sim_0, sim_1])
    assert not next(f for f in results[0].flags if f.flag_name == "LOW_ENSEMBLE_RETENTION").triggered
    assert next(f for f in results[1].flags if f.flag_name == "LOW_ENSEMBLE_RETENTION").triggered

def test_18_19_20_no_ranking_feature3_attribution():
    conf = _run_engine()[0]
    assert not hasattr(conf, "posterior_rank")
    assert not hasattr(conf, "Feature3")
    assert not hasattr(conf, "attribution_score")
    assert not hasattr(conf, "winner")
