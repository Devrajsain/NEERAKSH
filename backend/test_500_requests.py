import requests
import traceback

def run_test():
    print("Testing against running server at localhost:8000 with test_mode=false")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/cases/",
            data={
                "name": "Test Case",
                "location_name": "Test Location",
                "test_mode": "false"
            },
            files={
                "image_file": ("test.png", b"dummy image data", "image/png"),
                "csv_file": ("test.csv", b"dummy csv data", "text/csv")
            }
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print("Caught exception:")
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
