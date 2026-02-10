
import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def verify_dbscan_is_transnational():
    print("Verifying Transnational DBSCAN...\n")
    
    # 1. Anomalies (Should allow domestic)
    print("1. Checking Anomalies (Expect Domestic OK)...")
    try:
        r1 = requests.get(f"{BASE_URL}/anomalies?lookback_days=7&sigma=2.0")
        data1 = r1.json()
        anoms1 = data1.get("anomalies", [])
        
        has_cleveland = False
        for a in anoms1:
            if "Cleveland" in a['location'] or "United States" in a['location']:
                has_cleveland = True
                print(f"  -> Found Domestic Anomaly: {a['location']}")
                break
        
        if not has_cleveland:
            print("  -> WARNING: No domestic anomalies found. (Maybe data changed?)")
        else:
            print("  -> OK: Domestic anomalies present.")
            
    except Exception as e:
        print(f"  -> Failed to fetch anomalies: {e}")

    # 2. DBSCAN (Should be Transnational Only)
    print("\n2. Checking DBSCAN (Expect Transnational Only)...")
    try:
        # clustering=dbscan forces transnational=True in backend
        r2 = requests.get(f"{BASE_URL}/hotspots?clustering=dbscan&dbscan_eps=50&dbscan_min_samples=3")
        data2 = r2.json()
        
        # Structure is { "hotspots": { "location": [...], "event": [...], "actor": [...] } }
        loc_clusters = data2.get("hotspots", {}).get("location", [])
        
        print(f"  -> Found {len(loc_clusters)} DBSCAN clusters.")
        
        domestic_cluster_found = False
        for c in loc_clusters:
            loc_name = c.get("name", "Unknown")
            print(f"  -> Cluster: {loc_name} (Count: {c['count']})")
            
            # Heuristic check for Cleveland/Ohio/US-US domestic
            if "Cleveland" in loc_name or ("United States" in loc_name and "Israel" not in loc_name):
                # How to know if it's domestic?
                # Check top sources?
                # If backend filtered correctly, this cluster shouldn't exist IF it's purely domestic
                domestic_cluster_found = True
                
        if domestic_cluster_found:
            print("  -> FAIL: Domestic cluster found in DBSCAN results (Filter failed).")
        else:
            print("  -> SUCCESS: No obvious domestic clusters found.")
            
    except Exception as e:
        print(f"  -> Failed to fetch DBSCAN data: {e}")

if __name__ == "__main__":
    time.sleep(5) # Wait for startup
    verify_dbscan_is_transnational()
