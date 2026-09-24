import requests
import os
from datetime import date

url = "https://www.amfiindia.com/spages/NAVAll.txt"

headers = {
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
}

print("Fetching NAV data...")
try:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    print(f"HTTP error: {e}")
    exit()
except requests.exceptions.ConnectionError:
    print("Connection failed — check your internet.")
    exit()
except requests.exceptions.Timeout:
    print("Request timed out.")
    exit()

content = response.text
print(f"Response length: {len(content)} characters")

lines = content.splitlines()
print("\nFirst 5 lines:")
for line in lines[:5]:
    print(line)

today = date.today().strftime("%Y%m%d")
filepath = f"data/raw/nav_raw_{today}.txt"

os.makedirs("data/raw", exist_ok=True)
with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nSaved to {filepath}")
