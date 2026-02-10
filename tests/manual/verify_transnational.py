
import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def verify_transnational():
    print("Verifying Transnational Filtering...\n")
    
    # 1. Get Default (Domestic + International)
    print("Fetching Default Data...")
    try:
        r1 = requests.get(f"{BASE_URL}/anomalies?lookback_days=7&sigma=2.0")
        data1 = r1.json()
        anoms1 = data1.get("anomalies", [])
        print(f"  -> Default Anomalies: {len(anoms1)}")
        if anoms1:
            print(f"  -> Top: {anoms1[0]['location']}")
    except:
        print("  -> Failed to fetch default data")
        return

    # 2. Get Transnational Only
    print("\nFetching Transnational Data (transnational=true)...")
    try:
        r2 = requests.get(f"{BASE_URL}/anomalies?lookback_days=7&sigma=2.0&transnational=true")
        data2 = r2.json()
        anoms2 = data2.get("anomalies", [])
        print(f"  -> Transnational Anomalies: {len(anoms2)}")
        
        if len(anoms2) < len(anoms1):
            print("  -> SUCCESS: Count reduced (Noise filtered out).")
        else:
            print("  -> WARNING: Count same or higher (Filter might not be working).")
            
        print("\nTransnational Anomalies Found:")
        for a in anoms2:
            print(f"  - {a['location']} (Z={a['z_score']})")
            
    except Exception as e:
        print(f"  -> Failed to fetch transnational data: {e}")

if __name__ == "__main__":
    # Wait for server reload if needed
    time.sleep(2)
    verify_transnational()
