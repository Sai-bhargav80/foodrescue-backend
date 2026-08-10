import requests, json

# 1. Login as admin with correct credentials
r = requests.post('http://localhost:8000/admin/login', json={'email':'admin@foodrescue.com','password':'Admin@1234'})
print("Login Status:", r.status_code)
login_data = r.json()
token = login_data.get('token', '')
print("Token received:", bool(token))

# 2. Call dashboard overview with the token
r2 = requests.get('http://localhost:8000/api/v1/admin/dashboard/overview', 
                   headers={'Authorization': f'Bearer {token}'})
print("\nDashboard Status:", r2.status_code)
print("Dashboard Response:", json.dumps(r2.json(), indent=2)[:800])
