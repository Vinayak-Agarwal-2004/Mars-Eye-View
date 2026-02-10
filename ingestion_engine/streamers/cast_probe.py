import requests
import json
from datetime import datetime

TOKEN_URL = "https://acleddata.com/oauth/token"
CAST_URL = "https://acleddata.com/api/cast/read"

ACLED_EMAIL = "f20220827@pilani.bits-pilani.ac.in"
ACLED_KEY = "WfM#UnsQyg*W74T"

def get_access_token(username, password):
    print("Authenticating with ACLED...")
    headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
    data = {
        'username': username,
        'password': password,
        'grant_type': "password",
        'client_id': "acled"
    }
    
    try:
        resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
        resp.raise_for_status()
        token_data = resp.json()
        return token_data.get('access_token')
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

def fetch_cast_data():
    token = get_access_token(ACLED_EMAIL, ACLED_KEY)
    if not token: return

    print(f"Fetching CAST Forecasts...")
    
    # Try to fetch forecasts for 2025 or 2026
    params = {
        "year": "2025|2026",
        "year_where": "BETWEEN",
        "limit": 10
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "SufferingTracker/1.0"
    }
    
    try:
        # Note: Docs say /api/cast/ but usually it's /api/cast/read or similar structure.
        # Docs link says: https://acleddata.com/api/cast/ 
        # But 'read' is standard ACLED convention. Let's try base first or with read.
        # Actually standard is usually /api/dataset/read. 
        # Let's try https://acleddata.com/api/cast/read based on pattern.
        
        resp = requests.get(CAST_URL, params=params, headers=headers, timeout=30)
        
        # If 404, might be just /api/cast/
        if resp.status_code == 404:
             print("404 on /read, trying base /api/cast/")
             resp = requests.get("https://acleddata.com/api/cast/", params=params, headers=headers, timeout=30)
             
        resp.raise_for_status()
        data = resp.json()
        
        print(f"DEBUG RESPONSE: {json.dumps(data, indent=2)[:500]}...")
        
        val = data.get('data', [])
        print(f"Fetched {len(val)} CAST items.")
        
    except Exception as e:
        print(f"CAST Fetch Error: {e}")
        try: print(resp.text)
        except: pass

if __name__ == "__main__":
    fetch_cast_data()
