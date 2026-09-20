import pytest
import pandas as pd
import tempfile
import os
from datetime import datetime, timezone, timedelta
from app.tasks.pipeline import execute_5step_pipeline
from app.bayesian.schemas import FinalAttributionReport

def test_final_audit_e2e():
    """
    11. FINAL END-TO-END TEST
    Perform one synthetic end-to-end test using:
    3 unique MMSIs with deliberately different observation counts:
    MMSI A -> 3 observations
    MMSI B -> 7 observations
    MMSI C -> 12 observations
    Use different SOG, COG, trajectory positions, timestamps.
    """
    # 1. Create a synthetic AIS CSV
    ais_data = []
    # Match the TIFF timestamp (2024-01-15 10:00:00 detection, so AIS from 2024-01-14 22:00 to 10:00)
    t_start = datetime(2024, 1, 15, 6, 0, tzinfo=timezone.utc)
    
    # 3 unique MMSIs, varying N, varying SOG/COG
    # Match the TIFF bounding box (lat 41.0-41.9, lon 1.8-3.1)
    for mmsi, count, base_lat, base_sog in [("111", 3, 41.4, 10.0), ("222", 7, 41.45, 15.0), ("333", 12, 41.5, 20.0)]:
        for i in range(count):
            ais_data.append({
                "mmsi": mmsi,
                "timestamp": (t_start + timedelta(minutes=i*10)).isoformat(),
                "latitude": base_lat + (i * 0.001),
                "longitude": 2.5 + (i * 0.001),
                "sog": base_sog + i,
                "cog": float(i * 10),
                "vessel_name": f"Vessel_{mmsi}",
                "vessel_type": "Tanker"
            })
            
    df = pd.DataFrame(ais_data)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        csv_path = f.name
        
    # We will use an existing valid TIFF from the test uploads folder to ensure Feature 1 passes.
    # The pipeline requires a TIFF for spatial boundaries and spill parsing.
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    uploads_dir = os.path.join(base_dir, "uploads")
    import glob
    image_paths = glob.glob(os.path.join(uploads_dir, "*synthetic_oil_spill*.tif"))
    assert len(image_paths) > 0
    image_path = image_paths[0]
    
    try:
        # Run the full pipeline
        summary = execute_5step_pipeline(
            case_id="SLK-AUDIT",
            image_path=image_path,
            csv_path=csv_path,
            center_lat=41.5,
            center_lon=2.5,
            observation_time="2024-01-15T12:00:00Z",
            allow_test_fixture=True
        )
        
        # Verify 3 vessel candidates
        assert "bayesian_report" in summary
        report = FinalAttributionReport.model_validate(summary["bayesian_report"])
        
        assert report.status == "SUCCESS"
        assert report.returned_candidate_count == 3
        
        mmsi_list = [c.mmsi for c in report.candidates]
        assert "111" in mmsi_list
        assert "222" in mmsi_list
        assert "333" in mmsi_list
        
        for c in report.candidates:
            assert c.candidate_id == c.mmsi
            # verify feature 3 output doesn't contain 'score' or 'ranking'
            # (already enforced by Pydantic model FinalAttributionReport)
            
    finally:
        os.remove(csv_path)

