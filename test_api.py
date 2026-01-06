import requests
import time

BASE_URL = 'http://localhost:8081'

def test_check_api():
    print("Testing /check API...")
    
    # 1. Valid Checkin
    payload = {'uid': 'card_001', 'room': 'p1'}
    try:
        res = requests.post(f"{BASE_URL}/check", json=payload)
        print(f"Checkin Request: {res.status_code}, Response: {res.json()}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 2. Invalid UID
    payload = {'uid': 'invalid_card', 'room': 'p1'}
    try:
        res = requests.post(f"{BASE_URL}/check", json=payload)
        print(f"Invalid UID Request: {res.status_code}, Response: {res.json()}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 3. Invalid Room
    payload = {'uid': 'card_002', 'room': 'p2'} # staff1 allowed only p1
    try:
        res = requests.post(f"{BASE_URL}/check", json=payload)
        print(f"Invalid Room Request: {res.status_code}, Response: {res.json()}")
    except Exception as e:
        print(f"Request failed: {e}")
        
    print("Done.\n")

def test_emergency_api():
    print("Testing /emegency API...")
    try:
        res = requests.post(f"{BASE_URL}/emegency")
        print(f"Emergency Request: {res.status_code}")
    except Exception as e:
        print(f"Request failed: {e}")
    print("Done.\n")

if __name__ == '__main__':
    print("Ensure the server is running on localhost:8081 before running this script.")
    test_check_api()
    
    val = input("Do you want to trigger Emergency mode? (y/n): ")
    if val.lower() == 'y':
        test_emergency_api()
