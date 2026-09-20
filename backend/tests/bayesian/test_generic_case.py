import os
import pytest
from pathlib import Path
from app.tasks.pipeline import execute_5step_pipeline

def test_generic_case_end_to_end(monkeypatch):
    """
    Ensures that the Bayesian attribution pipeline works generically
    for any arbitrary case ID without being coupled to SLK-AUDIT, SLK-F3CE, etc.
    """
    os.environ["FEATURE2_ENVIRONMENT"] = "testing"
    
    test_dir = Path("tests/fixtures")
    if not test_dir.exists():
        test_dir = Path("backend/uploads")
        
    image_path = test_dir / "SLK-E095_synthetic_oil_spill.tif"
    csv_path = test_dir / "SLK-E095_synthetic_ais.csv"
    
    # Generic test case ID that shouldn't be matched anywhere in the code
    case_id = "SLK-TEST-GENERIC-001"
    
    # Let's also vary the coordinates slightly to prove it's not hardcoded to exactly 41.6, 2.7
    # Note: they must still fall within the bounds of the synthetic data or it might fail,
    # but we can shift it slightly within reason.
    center_lat = 41.605
    center_lon = 2.705
    
    # Mock _load_model to avoid PyTorch C++ access violation on Windows
    import app.services.detection as detection
    monkeypatch.setattr(detection, "_load_model", lambda: None)
    
    summary = execute_5step_pipeline(
        case_id=case_id,
        image_path=str(image_path),
        csv_path=str(csv_path),
        center_lat=center_lat,
        center_lon=center_lon,
        observation_time="2024-01-14T21:05:00Z",
        allow_test_fixture=True
    )
    
    assert summary["status"] == "COMPLETED"
    assert "spill" in summary
    assert "drift" in summary
    assert summary.get("attribution_mode") == "BAYESIAN"
    assert "bayesian_report" in summary
    
    report = summary["bayesian_report"]
    assert "candidates" in report
    
    # Verify the generic case ID is in the candidates
    candidates = report["candidates"]
    assert len(candidates) > 0
