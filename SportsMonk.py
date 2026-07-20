import json
import requests

# 1. Paste your Sportmonks API token here
API_TOKEN = "BKbNsUp8B5m6ZvbwItnvYyUQgr2Xg7YCBeJPUJ6nzsR4kZMtFqaFOfgj8N9y"

# 2. Set the base URL for the Football v3 API (using 'leagues' as a safe test)
url = "https://api.sportmonks.com/v3/motorsport/leagues/501"

# 3. Pass the token as a query parameter
params = {
    "api_token": API_TOKEN,
    "include": "currentSeason" 
}

try:
    print("Connecting to Sportmonks API...")
    response = requests.get(url, params=params)

    # Print HTTP Status Code (200 means success)
    print(f"Status Code: {response.status_code}\n")

    if response.status_code == 200:
        data = response.json()
        print("Success! Here is a sample of your returned data:\n")

        if "data" in data and len(data["data"]) > 0:
            print(json.dumps(data["data"][0], indent=2))
        else:
            print(json.dumps(data, indent=2))

    elif response.status_code in [401, 403]:
        print(
            "Access Denied: Your API token is either invalid, or your plan does not cover this endpoint."
        )
        print("Error details:", response.text)
    elif response.status_code == 429:
        print("Rate Limit Exceeded: You are making too many requests per hour.")
    else:
        print(f"Unexpected Error ({response.status_code}):", response.text)

except Exception as e:
    print(f"Connection failed: {e}")