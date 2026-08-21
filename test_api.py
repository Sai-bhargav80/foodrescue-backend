import requests
resp = requests.post("https://foodrescue-backend-thcu.onrender.com/signup", json={"email": "test8@test.com", "password": "password", "name": "Test", "mpin": "1234", "securityAnswer": "test"})
print(resp.status_code)
print(resp.text)
