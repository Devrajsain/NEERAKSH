import traceback
from fastapi.testclient import TestClient
from app.main import app
import sys

client = TestClient(app)

try:
    response = client.post(
        "/api/v1/cases/",
        data={
            "name": "Test Case Browser",
            "location_name": "Unknown Maritime Area",
            "test_mode": "true"
        },
        files={
            "image_file": ("SLK-E095_synthetic_oil_spill.tif", b"dummy_content", "image/tiff"),
            "csv_file": ("SLK-E095_browser_positive_ais.csv", b"dummy_csv", "text/csv"),
        }
    )
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
except Exception as e:
    print("EXCEPTION CAUGHT BY TEST SCRIPT:")
    traceback.print_exc()
