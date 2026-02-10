
import requests
import json

BASE_URL = "http://localhost:8000/api"

def debug_cleveland():
    print("Fetching History features to find Cleveland events...\n")
    try:
        # Get all history
        r = requests.get(f"{BASE_URL}/history?hours=168")
        data = r.json()
        features = data.get("features", [])
        
        # Filter for Cleveland
        cleveland_events = []
        for f in features:
            props = f.get("properties", {})
            name = props.get("countryname") or "" 
            # In anomaly, location name comes from daily_counts location_names map
            # We don't have grid logic here, but we can check name/actiongeo
            
            # Cleveland is 38:-76 grid? No.
            # Let's just look for "Cleveland" in actiongeo
            geo = props.get("countryname", "") # This field is mapped to ActionGeo in ingestion
            if "Cleveland" in geo:
                cleveland_events.append(f)
        
        print(f"Found {len(cleveland_events)} potential Cleveland events.")
        
        for i, f in enumerate(cleveland_events[:5]):
            p = f['properties']
            print(f"\nEvent #{i+1}:")
            print(f"  Name: {p.get('name')}")
            print(f"  A1 Code: '{p.get('actor1countrycode')}'")
            print(f"  A2 Code: '{p.get('actor2countrycode')}'")
            print(f"  Geo Code: '{p.get('actiongeo_countrycode')}'")
            print(f"  Source: {p.get('sourceurl')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_cleveland()
