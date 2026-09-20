import os
import glob
import pytest
from app.tasks.pipeline import execute_5step_pipeline
from app.bayesian.schemas import FinalAttributionReport

def test_synthetic_integration():
    """
    Test end-to-end integration of the Bayesian pipeline using the synthetic dataset.
    This ensures that the test_mode flag correctly routes the synthetic TIFF and AIS CSV
    through the Bayesian Orchestrator, bypassing heuristics-only pipelines.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    uploads_dir = os.path.join(base_dir, "uploads")
    
    # Dynamically find the synthetic test files in uploads directory
    image_paths = glob.glob(os.path.join(uploads_dir, "*synthetic_oil_spill*.tif"))
    csv_paths = glob.glob(os.path.join(uploads_dir, "*synthetic_ais*.csv"))
    
    assert len(image_paths) > 0, "No synthetic TIFF file found in uploads directory"
    assert len(csv_paths) > 0, "No synthetic AIS CSV found in uploads directory"
    
    # Sort to ensure deterministic selection
    image_paths.sort()
    csv_paths.sort()
    
    image_path = image_paths[0]
    csv_path = csv_paths[0]
    
    # We explicitly pass allow_test_fixture=True to simulate the frontend checkbox
    # We use a case_id that does NOT have 'TEST' or 'DEMO' to prove the gate is fixed
    summary = execute_5step_pipeline(
        case_id="SLK-F3CE",
        image_path=image_path,
        csv_path=csv_path,
        center_lat=None,
        center_lon=None,
        observation_time="2024-01-14T21:05:00Z",
        allow_test_fixture=True
    )
    
    # Check that is_test_mode and attribution_mode are correct
    assert summary.get("is_test_mode") is True
    assert summary.get("attribution_mode") == "BAYESIAN"

    # Feature1 Assertions
    spill_res = summary.get("spill", {})
    assert spill_res.get("status") != "DATA_UNAVAILABLE"
    assert spill_res.get("polygon_geojson") is not None
    assert spill_res.get("spill_latitude") is not None
    assert spill_res.get("spill_longitude") is not None
    assert spill_res.get("observation_time") is not None

    # Feature2 Assertions
    drift_res = summary.get("drift", {})
    assert drift_res.get("status") == "COMPLETED"
    assert drift_res.get("origin_latitude") is not None
    assert drift_res.get("origin_longitude") is not None
    assert len(drift_res.get("drift_trajectory", [])) > 0
    
    feature2_res = summary.get("feature2", {})
    assert feature2_res.get("status") == "COMPLETED"
    assert "forecast" in feature2_res
    
    # Feature3 Assertions
    assert summary.get("attribution_status") == "COMPLETED"
    assert len(summary.get("vessels", [])) > 0
    
    # The pipeline should output a bayesian_report dictionary
    assert "bayesian_report" in summary
    assert summary["bayesian_report"] is not None
    
    # Validate it against the schema
    report = FinalAttributionReport.model_validate(summary["bayesian_report"])
    
    assert report.status == "SUCCESS"
    assert report.returned_candidate_count > 0
    
    # Check that at least one candidate has a positive posterior probability
    positive_posterior_found = False
    
    mmsi_counts = {}
    
    for c_dict in summary["bayesian_report"]["candidates"]:
        # Verify no "score" or ranking field exists in the raw output
        forbidden_keys = ["attribution_score", "composite_attribution_score", "ranking", "rank", "winner", "top_candidate", "selected_candidate", "score"]
        for fk in forbidden_keys:
            assert fk not in c_dict, f"Forbidden key '{fk}' found in Bayesian candidate"
            
    for candidate in report.candidates:
        if candidate.posterior_probability > 0.0:
            positive_posterior_found = True
        
        mmsi_counts.setdefault(candidate.mmsi, []).append(candidate)
            
    assert positive_posterior_found, "No candidate was found with a positive posterior probability."
    
    # Check that candidate_ids are exactly the MMSI and are completely unique
    assert len(mmsi_counts) == len(report.candidates), "All candidates must have unique MMSIs"
    for candidate in report.candidates:
        assert candidate.candidate_id == candidate.mmsi, "Candidate ID must equal MMSI"

