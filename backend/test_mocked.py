import sys
import os
import traceback
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Patch before importing app.main so we don't have to wait for heavy stuff if it loads lazily, 
# or at least we avoid running it. Actually, app.main might import models at top level.
# If so, we have to wait. But let's patch execute_5step_pipeline.

def mock_execute_5step_pipeline(case_id, image_path, csv_path, center_lat, center_lon, observation_time=None, allow_test_fixture=False):
    return {
        "case_id": case_id,
        "status": "AWAITING_COORDINATES",
        "spill": {
            "area_km2": 12.3,
            "confidence_score": 0.85
        },
        "drift": None,
        "vessels": [],
        "feature2": {"status": "SKIPPED", "message": "Awaiting valid geographic coordinates"},
        "processed_at": "2026-09-20 00:00:00 UTC",
    }

with patch("app.routers.cases.execute_5step_pipeline", side_effect=mock_execute_5step_pipeline):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    def run():
        print("Sending browser-like request...")
        files = {
            'image_file': ('dummy.png', b'fake image data', 'image/png'),
            'csv_file': ('dummy.csv', b'fake csv data', 'text/csv'),
        }
        data = {
            'name': 'Test Case',
            'location_name': 'Test Location',
            'test_mode': 'true'
        }
        
        try:
            response = client.post("/api/v1/cases/", data=data, files=files)
            print(f"Status code: {response.status_code}")
            print(f"Response text: {response.text}")
        except Exception as e:
            print("Exception caught!")
            traceback.print_exc()

    if __name__ == "__main__":
        run()
