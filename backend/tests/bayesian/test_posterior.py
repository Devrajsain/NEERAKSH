import pytest
import math
from datetime import datetime, timezone

from app.bayesian.schemas import (
    CandidateGenerationResult,
    BayesianCandidateHypothesis,
    CandidateLikelihood,
    BayesianPosteriorResult
)
from app.bayesian.posterior import BayesianPosteriorEngine

def _create_candidates(priors):
    candidates = []
    for i, p in enumerate(priors):
        candidates.append(
            BayesianCandidateHypothesis(
                candidate_id=f"c{i}",
                mmsi=f"11122233{i}",
                release_position={"latitude": 0.0, "longitude": 0.0},
                release_time=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
                prior_probability=p
            )
        )
    return CandidateGenerationResult(
        candidate_count=len(priors),
        total_valid_candidates=len(priors),
        prior_candidate_count=len(priors),
        candidates=candidates
    )

def _create_likelihoods(log_likelihoods):
    likelihoods = []
    for i, ll in enumerate(log_likelihoods):
        L = math.exp(ll) if ll > float('-inf') else 0.0
        likelihoods.append(
            CandidateLikelihood(
                candidate_id=f"c{i}",
                likelihood_mode="gaussian",
                likelihood=L,
                log_likelihood=ll,
                observation_count=1
            )
        )
    return likelihoods

def test_basic_bayesian_calculation():
    # A1. Uniform prior + equal likelihood
    engine = BayesianPosteriorEngine()
    cg = _create_candidates([0.5, 0.5])
    lh = _create_likelihoods([-2.0, -2.0])
    res = engine.compute_posterior(cg, lh)
    assert res.status == "SUCCESS"
    assert math.isclose(res.posteriors[0].posterior_probability, 0.5)
    assert math.isclose(res.posteriors[1].posterior_probability, 0.5)
    
    # A2. Uniform prior + unequal likelihood
    cg = _create_candidates([0.5, 0.5])
    lh = _create_likelihoods([-2.0, float('-inf')])
    res = engine.compute_posterior(cg, lh)
    assert res.status == "SUCCESS"
    assert math.isclose(res.posteriors[0].posterior_probability, 1.0)
    assert res.posteriors[1].posterior_probability == 0.0
    
    # A3. Non-uniform prior
    cg = _create_candidates([0.2, 0.8])
    lh = _create_likelihoods([-2.0, -2.0]) # equal likelihood
    res = engine.compute_posterior(cg, lh)
    assert res.status == "SUCCESS"
    assert math.isclose(res.posteriors[0].posterior_probability, 0.2)
    assert math.isclose(res.posteriors[1].posterior_probability, 0.8)

def test_zero_likelihood():
    engine = BayesianPosteriorEngine()
    
    # B4. Some candidates zero likelihood
    cg = _create_candidates([0.5, 0.5])
    lh = _create_likelihoods([-2.0, float('-inf')])
    res = engine.compute_posterior(cg, lh)
    assert res.status == "SUCCESS"
    assert math.isclose(res.posteriors[0].posterior_probability, 1.0)
    assert res.posteriors[1].posterior_probability == 0.0

    # B5 & B6. All candidates zero likelihood & log_likelihood = -inf
    cg = _create_candidates([0.5, 0.5])
    lh = _create_likelihoods([float('-inf'), float('-inf')])
    res = engine.compute_posterior(cg, lh)
    assert res.status == "NO_POSITIVE_LIKELIHOOD"
    assert res.posteriors[0].posterior_probability == 0.0
    assert res.posteriors[1].posterior_probability == 0.0
    assert res.normalization_constant == 0.0
    assert res.log_normalization_constant == float('-inf')

def test_numerical_stability():
    engine = BayesianPosteriorEngine()
    # C7 & C8. Very small likelihoods / Large log-likelihood differences
    cg = _create_candidates([0.5, 0.5])
    lh = _create_likelihoods([-10.0, -1000.0])
    res = engine.compute_posterior(cg, lh)
    assert res.status == "SUCCESS"
    # C9. No NaN / inf
    assert math.isfinite(res.posteriors[0].posterior_probability)
    assert math.isfinite(res.posteriors[1].posterior_probability)
    assert res.posteriors[0].posterior_probability > 0.99
    assert res.posteriors[1].posterior_probability < 0.01

def test_candidate_alignment():
    engine = BayesianPosteriorEngine()
    cg = _create_candidates([0.5, 0.5])
    
    # D10. Matching candidate IDs (Already covered in other tests)
    
    # D11. Missing candidate likelihood
    lh_missing = _create_likelihoods([-2.0]) # Only c0
    res = engine.compute_posterior(cg, lh_missing)
    assert res.status == "VALIDATION_ERROR"
    assert any("missing likelihood" in e for e in res.errors)
    
    # D13. Extra unknown candidate likelihood
    lh_extra = _create_likelihoods([-2.0, -2.0, -2.0]) # c0, c1, c2
    res = engine.compute_posterior(cg, lh_extra)
    assert res.status == "VALIDATION_ERROR"
    assert any("unknown candidates" in e for e in res.errors)
    
    # D12. Duplicate likelihood
    lh_dup = _create_likelihoods([-2.0, -2.0])
    lh_dup[1].candidate_id = "c0" # Make duplicate
    # Make sure we don't have missing candidates so it ONLY triggers duplicate logic
    cg_dup = _create_candidates([0.5]) 
    res = engine.compute_posterior(cg_dup, lh_dup)
    assert res.status == "VALIDATION_ERROR"
    assert any("Duplicate likelihood" in e for e in res.errors)

def test_truncation():
    engine = BayesianPosteriorEngine()
    
    # E14. hypothesis_space_truncated = false
    cg = _create_candidates([0.5, 0.5])
    cg.hypothesis_space_truncated = False
    lh = _create_likelihoods([-2.0, -2.0])
    res = engine.compute_posterior(cg, lh)
    assert not res.hypothesis_space_truncated
    
    # E15, E16, E17. hypothesis_space_truncated = true
    cg.hypothesis_space_truncated = True
    cg.candidate_limit = 2
    cg.total_valid_candidates = 10
    res = engine.compute_posterior(cg, lh)
    assert res.hypothesis_space_truncated
    assert res.candidate_limit == 2
    assert res.total_valid_candidates == 10
    assert res.returned_candidate_count == 2
    # Ensure probabilities are still normalized to 1 over the truncated set
    assert math.isclose(res.posterior_sum, 1.0)

def test_normalization():
    engine = BayesianPosteriorEngine()
    cg = _create_candidates([0.2, 0.8])
    lh = _create_likelihoods([-3.0, -1.0])
    res = engine.compute_posterior(cg, lh)
    
    # F18. Posterior sum approximately 1
    assert math.isclose(res.posterior_sum, 1.0)
    
    # F19 & F20. Normalization constants
    w0 = 0.2 * math.exp(-3.0)
    w1 = 0.8 * math.exp(-1.0)
    expected_Z = w0 + w1
    assert math.isclose(res.normalization_constant, expected_Z)
    assert math.isclose(res.log_normalization_constant, math.log(expected_Z))

def test_isolation():
    engine = BayesianPosteriorEngine()
    cg = _create_candidates([1.0])
    lh = _create_likelihoods([-2.0])
    res = engine.compute_posterior(cg, lh)
    
    # G21-G24. No ranking, no confidence, etc.
    assert not hasattr(res, "posterior_rank")
    assert not hasattr(res, "winner")
    assert not hasattr(res, "confidence_score")
    assert not hasattr(res, "Feature3")
    
    # Ensure CandidatePosterior doesn't have it either
    if res.posteriors:
        p = res.posteriors[0]
        assert not hasattr(p, "rank")
        assert not hasattr(p, "confidence")

def test_prior_validation():
    from pydantic import ValidationError
    engine = BayesianPosteriorEngine()
    
    # Negative prior (fails Pydantic validation)
    with pytest.raises(ValidationError):
        cg = _create_candidates([-0.5, 1.5])
    
    # Prior not summing to 1 (fails Engine validation)
    cg = _create_candidates([0.5, 0.4])
    lh = _create_likelihoods([-2.0, -2.0])
    res = engine.compute_posterior(cg, lh)
    assert res.status == "VALIDATION_ERROR"
    assert any("sum to 1.0" in e for e in res.errors)
    
    # Zero prior -> posterior 0
    cg = _create_candidates([0.0, 1.0])
    res = engine.compute_posterior(cg, lh)
    assert res.status == "SUCCESS"
    assert res.posteriors[0].posterior_probability == 0.0
    assert math.isclose(res.posteriors[1].posterior_probability, 1.0)
