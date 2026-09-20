from pathlib import Path
import sys

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))

from app.tasks.pipeline import execute_5step_pipeline
import logging

logging.basicConfig(level=logging.INFO)

def test_spill_res():
    base_dir = Path("backend").resolve()
    uploads_dir = base_dir / "uploads"
    image_path = uploads_dir / "SLK-E095_synthetic_oil_spill.tif"
    csv_path = uploads_dir / "SLK-E095_synthetic_ais.csv"
    
    from app.services.detection import run_spill_detection_model
    res = run_spill_detection_model(
        str(image_path),
        center_lat=41.6,
        center_lon=2.7,
        observation_time="2024-01-14T21:00:00Z",
        allow_test_fixture=True
    )
    print("Spill Detection Result:")
    for k, v in res.items():
        if k != "polygon_geojson":
            print(f"  {k}: {v}")

if __name__ == "__main__":
    test_spill_res()
