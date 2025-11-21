import requests
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0IiwiZXhwIjoxNzYzNzE2MjY2LCJ1aWQiOjQsInJvbGVzIjpbInVzZXIiXX0.hQoZ-UmM3ilRga7chXdW6xruVxYif92eLr6wHrByLDQ"
HEADERS = {"Authorization": "Bearer " + TOKEN}
resp = requests.get("http://127.0.0.1:8001/api/v1/user/service/individual/status", headers=HEADERS)
print(resp.status_code)
print(resp.text)
