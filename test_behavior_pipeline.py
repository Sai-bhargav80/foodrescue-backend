import requests

base_url = "http://localhost:8000/api/v1"

# 1. Post a normal gameplay log
payload_normal = {
    "player_id": 2,
    "action_type": "score_submission",
    "location": "37.7749,-122.4194",
    "metadata": {
        "score": 500.0,
        "device_fingerprint": "dev_test_fingerprint_01",
        "is_vpn": False
    }
}

print("Posting normal gameplay behavior log:")
r = requests.post(f"{base_url}/behavior/log", json=payload_normal)
print("Status:", r.status_code)
print("Response:", r.json())

# 2. Post a suspicious telemetry log (impossible travel / speed teleportation)
# Previous location: 37.7749, -122.4194 (San Francisco)
# New location: 40.7128, -74.0060 (New York)
# Distance: ~4100 km. Time difference: 0 seconds (speed = infinity!)
payload_teleport = {
    "player_id": 2,
    "action_type": "score_submission",
    "location": "40.7128,-74.0060",
    "metadata": {
        "score": 15000.0,  # Impossible score > 10,000!
        "device_fingerprint": "dev_test_fingerprint_01",
        "is_vpn": True
    }
}

print("\nPosting suspicious gameplay behavior log:")
r = requests.post(f"{base_url}/behavior/log", json=payload_teleport)
print("Status:", r.status_code)
print("Response:", r.json())

# 3. Verify user 2 details via local database query to see if trust_score dropped
import pymysql
connection = pymysql.connect(
    host="localhost",
    user="root",
    password="saibhargav123",
    database="food_rescue"
)
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, email, trust_score, status, isBanned, last_known_location FROM users WHERE id=2")
        print("\nDatabase values for User 2 after test logs:")
        print(cursor.fetchone())
finally:
    connection.close()
