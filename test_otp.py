import requests
resp = requests.post("https://foodrescue-backend-thcu.onrender.com/send-signup-otp", json={"email": "vemanisai@gmail.com"})
print(resp.status_code)
print(resp.text)
