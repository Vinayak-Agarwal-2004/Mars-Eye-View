
import requests
import json

BASE_URL = "http://localhost:8000/api"

def check_schema():
    print(f"Fetching history to check schema...")
    try:
        # Fetch a small chunk of history
        r = requests.get(f"{BASE_URL}/history?hours=1")
        data = r.json()
        features = data.get("features", [])
        
        if not features:
            print("No events found in last hour. Tying 24h...")
            r = requests.get(f"{BASE_URL}/history?hours=24")
            data = r.json()
            features = data.get("features", [])
            
        if features:
            print("\nFirst Event Properties:")
            props = features[0].get("properties", {})
            print(json.dumps(props, indent=2))
            
            # Check for country codes specifically
            print("\nCountry Code Check:")
            print(f"Actor1CountryCode: {props.get('actor1countrycode')}")
            print(f"Actor2CountryCode: {props.get('actor2countrycode')}")
            print(f"ActionGeo_CountryCode: {props.get('actiongeo_countrycode')}")
            print(f"ActionGeo_ADM1Code: {props.get('actiongeo_adm1code')}")
        else:
            print("No events found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
