import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.bayesian.orchestrator import BayesianPipelineOrchestrator
from app.bayesian.schemas import (
    BayesianPipelineRequest,
    CandidateGenerationResult,
    BayesianCandidateHypothesis,
    OpenOilSimulationResult,
    CandidateLikelihood,
    BayesianPosteriorResult,
    CandidatePosterior,
    PhysicsAwareConfidence,
    ParticleState
)


@pytest.fixture
def mock_orchestrator():
    prefilter = MagicMock()
    candidate_generator = MagicMock()
    simulation_runner = MagicMock()
    likelihood_engine = MagicMock()
    posterior_engine = MagicMock()
    confidence_engine = MagicMock()
    orchestrator = BayesianPipelineOrchestrator(
        currents_provider=MagicMock(provider_name="test_currents"),
        wind_provider=MagicMock(provider_name="test_wind")
    )
    orchestrator.prefilter_engine = prefilter
    orchestrator.simulation_runner = simulation_runner
    orchestrator.likelihood_engine = likelihood_engine
    orchestrator.posterior_engine = posterior_engine
    orchestrator.confidence_engine = confidence_engine
    return orchestrator

@patch("app.bayesian.orchestrator.generate_candidate_hypotheses")
def test_ensemble_statistics_wired_correctly(mock_generate, mock_orchestrator):
    # Setup mock returns
    mock_orchestrator.prefilter_engine.run_prefilter.return_value = MagicMock(role="SEARCH_PREFILTER_ONLY")
    
    candidate = BayesianCandidateHypothesis(
        candidate_id="cand_1",
        mmsi="123",
        release_position={"latitude": 41.0, "longitude": 2.0},
        release_time=datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc),
        prior_probability=1.0,
        observations=[]
    )
    mock_generate.return_value = CandidateGenerationResult(
        candidates=[candidate],
        status="SUCCESS",
        hypothesis_space_truncated=False,
        candidate_count=1,
        total_valid_candidates=1,
        prior_mode="uniform",
        prior_candidate_count=1
    )
    
    # Create mock particles that are slightly dispersed to test statistics calculation
    particles = [
        ParticleState(longitude=2.1, latitude=41.1, status="active", original_status_code=0),
        ParticleState(longitude=2.11, latitude=41.11, status="active", original_status_code=0)
    ]
    sim_result = OpenOilSimulationResult(
        candidate_id="cand_1",
        mmsi="123",
        status="SUCCESS",
        release_timestamp=candidate.release_time,
        requested_observation_timestamp=datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc),
        actual_final_timestamp=datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc),
        ensemble_size_requested=2,
        ensemble_size_returned=2,
        active_particle_count=2,
        final_particle_states=particles
    )
    mock_orchestrator.simulation_runner.run_candidate.return_value = sim_result
    
    likelihood = CandidateLikelihood(
        candidate_id="cand_1",
        likelihood=0.5,
        log_likelihood=-0.69,
        likelihood_mode="gaussian",
        observation_count=1
    )
    mock_orchestrator.likelihood_engine.evaluate.return_value = likelihood
    
    posterior = CandidatePosterior(
        candidate_id="cand_1",
        mmsi="123",
        release_latitude=41.0,
        release_longitude=2.0,
        release_timestamp=candidate.release_time,
        prior=1.0,
        likelihood=0.5,
        posterior_probability=1.0,
        likelihood_mode="gaussian",
        evaluation_status="SUCCESS"
    )
    posterior_result = BayesianPosteriorResult(
        status="SUCCESS",
        hypothesis_space_truncated=False,
        returned_candidate_count=1,
        evaluated_candidate_count=1,
        positive_likelihood_candidate_count=1,
        normalization_constant=1.0,
        posterior_sum=1.0,
        posteriors=[posterior],
        prior_mode="uniform"
    )
    mock_orchestrator.posterior_engine.compute_posterior.return_value = posterior_result
    
    mock_orchestrator.confidence_engine.compute_confidence.return_value = [
        PhysicsAwareConfidence(
            candidate_id="cand_1",
            confidence_level="INDETERMINATE",
            diagnostics=[],
            flags=[],
            posterior_probability=1.0,
            hypothesis_space_truncated=False
        )
    ]
    
    request = MagicMock()
    request.feature2_context = None
    request.spill_data.spill_id = "spill_1"
    request.spill_data.observation_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    request.bayesian_config = None
    
    # Run the pipeline
    mock_orchestrator.run_pipeline(request)
    
    # Verify compute_confidence was called with ensemble_stats
    mock_orchestrator.confidence_engine.compute_confidence.assert_called_once()
    kwargs = mock_orchestrator.confidence_engine.compute_confidence.call_args[1]
    
    assert "ensemble_stats" in kwargs
    ensemble_stats = kwargs["ensemble_stats"]
    assert "cand_1" in ensemble_stats
    
    stats = ensemble_stats["cand_1"]
    assert stats is not None
    assert stats.active_particle_count == 2
    assert stats.spread_radius_m > 0
    
@patch("app.bayesian.orchestrator.generate_candidate_hypotheses")
def test_missing_data_produces_none(mock_generate, mock_orchestrator):
    mock_orchestrator.prefilter_engine.run_prefilter.return_value = MagicMock(role="SEARCH_PREFILTER_ONLY")
    
    candidate = BayesianCandidateHypothesis(
        candidate_id="cand_1",
        mmsi="123",
        release_position={"latitude": 41.0, "longitude": 2.0},
        release_time=datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc),
        prior_probability=1.0,
        observations=[]
    )
    mock_generate.return_value = CandidateGenerationResult(
        candidates=[candidate], status="SUCCESS", hypothesis_space_truncated=False, candidate_count=1, total_valid_candidates=1, prior_mode="uniform", prior_candidate_count=1
    )
    
    # Simulation failed internally
    sim_result = OpenOilSimulationResult(
        candidate_id="cand_1",
        mmsi="123",
        status="ENVIRONMENTAL_DATA_INCOMPLETE",
        release_timestamp=candidate.release_time,
        requested_observation_timestamp=datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc),
        ensemble_size_requested=2,
    )
    mock_orchestrator.simulation_runner.run_candidate.return_value = sim_result
    mock_orchestrator.likelihood_engine.evaluate.return_value = CandidateLikelihood(candidate_id="cand_1", likelihood=0.0, likelihood_mode="gaussian", observation_count=1)
    mock_orchestrator.posterior_engine.compute_posterior.return_value = BayesianPosteriorResult(
        status="NO_POSITIVE_LIKELIHOOD", hypothesis_space_truncated=False, returned_candidate_count=1, evaluated_candidate_count=0,
        positive_likelihood_candidate_count=0, normalization_constant=0.0, posterior_sum=0.0, posteriors=[], prior_mode="uniform"
    )
    
    request = MagicMock()
    request.feature2_context = None
    request.spill_data.spill_id = "spill_1"
    request.spill_data.observation_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    request.bayesian_config = None
    
    mock_orchestrator.run_pipeline(request)
    
    kwargs = mock_orchestrator.confidence_engine.compute_confidence.call_args[1]
    ensemble_stats = kwargs["ensemble_stats"]
    assert ensemble_stats["cand_1"] is None
