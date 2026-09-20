import sys
import logging
from pathlib import Path

# Fix path to load backend app
backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=True)

image_path = backend_dir / "uploads" / "SLK-E095_synthetic_oil_spill.tif"
csv_path = backend_dir / "uploads" / "SLK-E095_synthetic_ais.csv"

# Configure python logging so we see the tracebacks
logging.basicConfig(level=logging.ERROR)

print("Making request...")
try:
    with TestClient(app, raise_server_exceptions=True) as client:
        with open(image_path, "rb") as img, open(csv_path, "rb") as csv:
            response = client.post(
                "/api/v1/cases/",
                data={
                    "name": "Test Upload",
                    "location_name": "Test Location",
                    "test_mode": "false"  # Ensure it uses real environmental data!
                },
                files={
                    "image_file": ("SLK-E095_synthetic_oil_spill.tif", img, "image/tiff"),
                    "csv_file": ("SLK-E095_synthetic_ais.csv", csv, "text/csv")
                }
            )
        print("Cases response status:", response.status_code)
        resp_json = response.json()
        case_id = resp_json["id"]
        print("Created case:", case_id)
        
        print("Calling Bayesian pipeline...")
        bayesian_response = client.post(f"/api/v1/bayesian/attribution_pipeline_by_case/{case_id}")
        print("Bayesian status:", bayesian_response.status_code)
        print("Bayesian output length:", len(bayesian_response.text))

except Exception as e:
    import traceback
    print("Caught Exception:", type(e).__name__)
    traceback.print_exc()


