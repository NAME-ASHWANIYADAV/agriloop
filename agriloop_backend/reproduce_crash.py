
import requests

url = "http://127.0.0.1:8000/api/webhook/whatsapp"
payload = {
    "From": "whatsapp:+919876543210",
    "Body": "Tell me about growing tomatoes",
    "ProfileName": "Test Farmer"
}

try:
    response = requests.post(url, data=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
