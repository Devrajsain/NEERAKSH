import pytest
import math
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.bayesian.schemas import (
    BayesianPosteriorResult,
    CandidatePosterior,
    PhysicsAwareConfidence,
    ConfidenceDiagnostic,
    ConfidenceFlag,
    AttributionProvenance,
    FinalAttributionReport,
    SupplementalDeterministicEvidence,
    FinalAttributionRequest
)
from app.bayesian.final_attribution import FinalAttributionEngine

# Need a basic FastAPI app to test the endpoint
from fastapi import FastAPI
from app.bayesian.api.routes import router as bayesian_router

test_app = FastAPI()
test_app.include_router(bayesian_router, prefix="/api/v1/bayesian")
client = TestClient(test_app)

def _create_base_posterior(candidate_id: str, mmsi: str, prob: float, status="SUCCESS") -> CandidatePosterior:
    return CandidatePosterior(
        candidate_id=candidate_id,
        mmsi=mmsi,
        release_latitude=0.0,
        release_longitude=0.0,
        release_timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc),
        prior=0.5,
        likelihood=0.5,
        log_likelihood=-1.0,
        unnormalized_log_weight=-2.0,
        posterior_probability=prob,
        likelihood_mode="gaussian",
        evaluation_status=status
    )

def _create_base_metadata(posteriors, status="SUCCESS", truncated=False) -> BayesianPosteriorResult:
    return BayesianPosteriorResult(
        status=status,
        hypothesis_space_truncated=truncated,
        candidate_limit=10,
        total_valid_candidates=20 if truncated else len(posteriors),
        returned_candidate_count=len(posteriors),
        prior_mode="UNIFORM",
        evaluated_candidate_count=len([p for p in posteriors if p.evaluation_status == "SUCCESS"]),
        positive_likelihood_candidate_count=len([p for p in posteriors if p.posterior_probability > 0]),
        normalization_constant=1.0,
        log_normalization_constant=0.0,
        posterior_sum=sum(p.posterior_probability for p in posteriors),
        posteriors=posteriors
    )

def _create_confidence(candidate_id: str, level="INDETERMINATE") -> PhysicsAwareConfidence:
    return PhysicsAwareConfidence(
        candidate_id=candidate_id,
        posterior_probability=0.0,
        confidence_level=level,
        hypothesis_space_truncated=False,
        candidate_limit=10,
        total_valid_candidates=10,
        returned_candidate_count=10,
        prior_mode="UNIFORM"
    )

def _create_prov() -> AttributionProvenance:
    return AttributionProvenance()

# 1. Single candidate preservation
def test_1_single_candidate():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 1.0)]
    meta = _create_base_metadata(posteriors)
    conf = [_create_confidence("c0")]
    report = engine.generate_report("s1", meta, conf, None, _create_prov())
    assert len(report.candidates) == 1
    assert report.candidates[0].candidate_id == "c0"
    assert report.candidates[0].mmsi == "123"

# 2. Multiple candidate preservation
def test_2_multiple_candidates():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 0.6), _create_base_posterior("c1", "456", 0.4)]
    meta = _create_base_metadata(posteriors)
    conf = [_create_confidence("c0"), _create_confidence("c1")]
    report = engine.generate_report("s1", meta, conf, None, _create_prov())
    assert len(report.candidates) == 2

# 3. Same MMSI + different hypotheses remain separate
def test_3_same_mmsi_distinct_hypotheses():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 0.6), _create_base_posterior("c1", "123", 0.4)]
    # Tweak timestamp so they are distinctly different hypotheses
    posteriors[1].release_timestamp = datetime(2026, 9, 2, tzinfo=timezone.utc)
    meta = _create_base_metadata(posteriors)
    conf = [_create_confidence("c0"), _create_confidence("c1")]
    report = engine.generate_report("s1", meta, conf, None, _create_prov())
    
    assert len(report.candidates) == 2
    c0 = next(c for c in report.candidates if c.candidate_id == "c0")
    c1 = next(c for c in report.candidates if c.candidate_id == "c1")
    assert math.isclose(c0.posterior_probability, 0.6)
    assert math.isclose(c1.posterior_probability, 0.4)

# 4. Equal posterior preservation
def test_4_similar_posterior_candidates():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 0.5), _create_base_posterior("c1", "456", 0.5)]
    meta = _create_base_metadata(posteriors)
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    assert report.candidates[0].posterior_probability == 0.5
    assert report.candidates[1].posterior_probability == 0.5

# 5. Truncation metadata + limitation
def test_5_truncation():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 1.0)]
    meta = _create_base_metadata(posteriors, truncated=True)
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    assert report.hypothesis_space_truncated
    assert any("evaluated candidate hypothesis set" in limit for limit in report.limitations)

# 6. NO_POSITIVE_LIKELIHOOD handling
def test_6_no_positive_likelihood():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 0.0)]
    meta = _create_base_metadata(posteriors, status="NO_POSITIVE_LIKELIHOOD")
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    assert report.status == "NO_POSITIVE_LIKELIHOOD"

# 7. Explicit EVALUATION_UNAVAILABLE handling & 8. Mixed statuses & 9. Verify unavailable_candidate_count == len(...)
def test_7_8_9_unavailable_evaluation_and_mixed_statuses():
    engine = FinalAttributionEngine()
    posteriors = [
        _create_base_posterior("c0", "123", 0.5, status="SUCCESS"),
        _create_base_posterior("c1", "456", 0.0, status="EVALUATION_UNAVAILABLE"),
        _create_base_posterior("c2", "789", 0.5, status="SOME_OTHER_STATUS")
    ]
    meta = _create_base_metadata(posteriors)
    # Manually fix counts because our helper sets them based on SUCCESS
    meta.evaluated_candidate_count = 2 # c0 and c2
    meta.returned_candidate_count = 3
    
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    
    assert report.unavailable_candidate_count == 1
    assert report.unavailable_candidate_ids == ["c1"]
    assert report.unavailable_candidate_count == len(report.unavailable_candidate_ids)

# 10. Missing Phase 6 confidence
def test_10_missing_phase6_confidence():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 1.0)]
    meta = _create_base_metadata(posteriors)
    
    report = engine.generate_report("s1", meta, [], None, _create_prov()) # Empty confidence list
    
    assert report.candidates[0].confidence_level == "INDETERMINATE"
    assert report.candidates[0].confidence_diagnostics == []
    assert report.candidates[0].confidence_flags == []
    assert any("Phase 6 physics-aware confidence data is missing" in w for w in report.warnings)

# 11. Existing Phase 6 confidence pass-through
def test_11_confidence_pass_through():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 1.0)]
    meta = _create_base_metadata(posteriors)
    conf = [_create_confidence("c0", level="INDETERMINATE")]
    report = engine.generate_report("s1", meta, conf, None, _create_prov())
    assert report.candidates[0].confidence_level == "INDETERMINATE"
    assert not any("Phase 6 physics-aware confidence data is missing" in w for w in report.warnings)

# 12. Confidence flags pass-through
def test_12_confidence_flags_mapping():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 1.0)]
    meta = _create_base_metadata(posteriors)
    conf = [_create_confidence("c0")]
    conf[0].flags.append(ConfidenceFlag(
        flag_name="TEST_FLAG", description="desc", severity="WARNING", triggered=True
    ))
    report = engine.generate_report("s1", meta, conf, None, _create_prov())
    assert report.candidates[0].confidence_flags[0].flag_name == "TEST_FLAG"

# 13. Posterior immutability using NONTRIVIAL values
def test_13_posterior_immutability():
    engine = FinalAttributionEngine()
    posteriors = [
        _create_base_posterior("c0", "123", 0.17),
        _create_base_posterior("c1", "456", 0.23),
        _create_base_posterior("c2", "789", 0.60),
    ]
    meta = _create_base_metadata(posteriors)
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    assert math.isclose(report.candidates[0].posterior_probability, 0.17)
    assert math.isclose(report.candidates[1].posterior_probability, 0.23)
    assert math.isclose(report.candidates[2].posterior_probability, 0.60)

# 14. Unavailable candidate does NOT trigger renormalization
def test_14_unavailable_does_not_renormalize():
    engine = FinalAttributionEngine()
    posteriors = [
        _create_base_posterior("c0", "123", 0.55),
        _create_base_posterior("c1", "456", 0.30, status="EVALUATION_UNAVAILABLE"),
        _create_base_posterior("c2", "789", 0.15),
    ]
    meta = _create_base_metadata(posteriors)
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    
    assert math.isclose(report.candidates[0].posterior_probability, 0.55)
    assert math.isclose(report.candidates[1].posterior_probability, 0.30)
    assert math.isclose(report.candidates[2].posterior_probability, 0.15)

# 15. Feature 3 isolation from posterior & 16. Feature 3 does not modify Phase 6 confidence
def test_15_16_feature3_isolation():
    f3_resp_dict = {
        "spill_id": "s1",
        "scoring_mode": "test",
        "candidate_count": 1,
        "vessels": [
            {
                "id": "v1", "mmsi": "123", "name": "V", "type": "T", "flag": "F",
                "overall_score": 85.5, "risk_class": "HIGH", "scoring_mode": "test",
                "scores": {"origin_presence": 100, "behavior_anomaly": 50, "dwell_time": 0, "ais_gap": 0, "applied_weights": {}},
                "evidence": {"closest_approach_distance_km": 0, "time_offset_minutes": 0, "inside_uncertainty_zone": False, "dwell_minutes_inside_zone": 0, "dwell_minutes_near_zone": 0},
                "explanation": "text", "current_latitude": 0, "current_longitude": 0, "heading_deg": 0, "speed_kts": "0"
            }
        ]
    }
    
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 0.75)]
    meta = _create_base_metadata(posteriors)
    conf = [_create_confidence("c0", level="INDETERMINATE")]
    
    from app.feature3.schemas import Feature3AttributionResponse
    f3_obj = Feature3AttributionResponse.model_validate(f3_resp_dict)
    
    report = engine.generate_report("s1", meta, conf, f3_obj, _create_prov())
    supp = report.candidates[0].supplemental_deterministic_evidence
    
    # 15. Feature 3 isolated
    assert supp.feature3_overall_score == 85.5
    assert report.candidates[0].posterior_probability == 0.75 # Unmodified
    
    # 16. Confidence unmodified
    assert report.candidates[0].confidence_level == "INDETERMINATE"

# 17. Provenance preservation
def test_17_provenance_preservation():
    engine = FinalAttributionEngine()
    meta = _create_base_metadata([])
    prov = AttributionProvenance(environmental_data_provider="CMEMS")
    report = engine.generate_report("s1", meta, [], None, prov)
    assert report.provenance.environmental_data_provider == "CMEMS"

# 18. No winner/top_candidate & 19. No rank/ranking
def test_18_19_absence_of_winner_field():
    engine = FinalAttributionEngine()
    meta = _create_base_metadata([])
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    assert not hasattr(report, "winner")
    assert not hasattr(report, "top_candidate")
    assert not hasattr(report, "rank")
    assert not hasattr(report, "ranking")
    assert not hasattr(report, "selected_candidate")

# 20. No final_score/attribution_score/etc
def test_20_absence_of_new_attribution_score():
    engine = FinalAttributionEngine()
    posteriors = [_create_base_posterior("c0", "123", 1.0)]
    meta = _create_base_metadata(posteriors)
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    cand = report.candidates[0]
    assert not hasattr(cand, "final_score")
    assert not hasattr(cand, "attribution_score")
    assert not hasattr(cand, "responsibility_score")
    assert not hasattr(cand, "confidence_score")
    assert not hasattr(cand, "weighted_score")

# 21. Candidate order is exactly preserved from Phase 5 input
def test_21_candidate_order_preserved():
    engine = FinalAttributionEngine()
    posteriors = [
        _create_base_posterior("c0", "123", 0.1),
        _create_base_posterior("c1", "456", 0.8),
        _create_base_posterior("c2", "789", 0.1)
    ]
    meta = _create_base_metadata(posteriors)
    report = engine.generate_report("s1", meta, [], None, _create_prov())
    
    assert report.candidates[0].candidate_id == "c0"
    assert report.candidates[1].candidate_id == "c1"
    assert report.candidates[2].candidate_id == "c2"

# 22. FastAPI endpoint schema works & 23. Verify response is FinalAttributionReport
def test_22_23_api_schema():
    posteriors = [_create_base_posterior("c0", "123", 1.0)]
    meta = _create_base_metadata(posteriors)
    conf = [_create_confidence("c0")]
    prov = _create_prov()

    req_data = {
        "spill_id": "s1",
        "posterior_result": meta.model_dump(mode="json"),
        "confidence_results": [c.model_dump(mode="json") for c in conf],
        "feature3_response": None,
        "provenance": prov.model_dump(mode="json")
    }
    
    resp = client.post("/api/v1/bayesian/bayesian_final_report", json=req_data)
    assert resp.status_code == 200
    
    # Verify response parses into FinalAttributionReport perfectly
    data = resp.json()
    report = FinalAttributionReport.model_validate(data)
    assert report.spill_id == "s1"
    assert len(report.candidates) == 1
