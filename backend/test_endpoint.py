import requests
import json

# Test the all-sections-workbook endpoint
try:
    response = requests.get("http://localhost:8000/timetables/all-sections-workbook")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 404:
        try:
            error_data = response.json()
            print("Error Response:")
            print(json.dumps(error_data, indent=2))
        except:
            print("Error Response (text):")
            print(response.text)
    else:
        print("Success! Response received.")
except requests.exceptions.ConnectionError:
    print("Backend server is not running. Please start the server first.")
except Exception as e:
    print(f"Error: {e}")