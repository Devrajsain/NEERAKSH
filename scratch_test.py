import os
import glob
import json
import sys
import unittest.mock as mock
sys.modules['torch'] = mock.MagicMock()

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.tasks.pipeline import execute_5step_pipeline

def run():
    base_dir = os.path.abspath('backend/uploads')
    image_paths = glob.glob(os.path.join(base_dir, "*synthetic_oil_spill*.tif"))
    csv_paths = glob.glob(os.path.join(base_dir, "*synthetic_ais*.csv"))
    
    if not image_paths or not csv_paths:
        print("Missing synthetic files.")
        return
        
    image_path = image_paths[0]
    csv_path = csv_paths[0]
    
    print(f"Using {image_path} and {csv_path}")
    
    # Try to disable torch import in detection.py to prevent crash
    # Oh wait, if torch is already imported it will crash. Let's just run and see.
    summary = execute_5step_pipeline(
        case_id="TEST_SYNTHETIC_001",
        image_path=image_path,
        csv_path=csv_path,
        center_lat=None,
        center_lon=None,
        observation_time=None,
        allow_test_fixture=True
    )
    
    rep = summary.get("bayesian_report")
    if not rep:
        print("No bayesian report!")
        return
        
    print(f"Status: {rep.get('status')}")
    if rep.get("status") == "VALIDATION_ERROR":
        print("Errors:")
        print(json.dumps(rep.get("errors", []), indent=2))
        print("Warnings:")
        print(json.dumps(rep.get("warnings", []), indent=2))

if __name__ == "__main__":
    run()
