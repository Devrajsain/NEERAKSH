import sys
import os
import traceback

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def run():
    print("Sending browser-like request with EMPTY STRINGS...")
    
    sample_img = os.path.join(settings.UPLOAD_DIR, "sample_sar_slick.png")
    sample_csv = "dummy.csv"
    
    with open(sample_img, "rb") as img_f, open(sample_csv, "rb") as csv_f:
        files = {
            'image_file': ('sample_sar_slick.png', img_f, 'image/png'),
            'csv_file': ('sample_ais_telemetry.csv', csv_f, 'text/csv'),
        }
        
        data = {
            'name': 'Test Case Empty Strings',
            'location_name': 'Test Location',
            'test_mode': 'true',
            'center_latitude': '',
            'center_longitude': '',
            'observation_time': ''
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
