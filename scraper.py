import requests
import os
from datetime import date
# the url where amfi posts nav data every day
url = "https://www.amfiindia.com/spages/NAVAll.txt"
# adding a user agent so the server doesnt block us
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
}
print("fetching nav data...")
try:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    print(f"http error: {e}")
    exit()
except requests.exceptions.ConnectionError:
    print("connection failed, check your internet")
    exit()
except requests.exceptions.Timeout:
    print("request timed out")
    exit()
content = response.text
# print some basic info + first 5 lines
print(f"response length: {len(content)} characters")
lines = content.splitlines()
print("\nfirst 5 lines:")
for line in lines[:5]:
    print(line)
# save with today's date
today = date.today().strftime("%Y%m%d")
filename = f"nav_raw_{today}.txt"

os.makedirs("data/raw", exist_ok=True)
filepath = f"data/raw/{filename}"

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nsaved to {filepath}")
