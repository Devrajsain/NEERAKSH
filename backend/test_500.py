import traceback
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_test():
    print("Testing browser request with None filename...")
    try:
        response = client.post(
            "/api/v1/cases/",
            data={
                "name": "Test Case",
                "location_name": "Operational Area", # to trigger the refinement logic!
                "test_mode": "true",
            },
            files={
                "image_file": (None, b"dummy", "image/png"),
            }
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print("Caught server exception:")
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
