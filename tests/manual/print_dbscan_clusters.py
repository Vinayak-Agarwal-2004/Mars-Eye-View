
import requests
import json

BASE_URL = "http://localhost:8000/api"

def print_dbscan_clusters():
    print(f"Fetching DBSCAN clusters from {BASE_URL}...\n")
    try:
        # Fetch data
        r = requests.get(f"{BASE_URL}/hotspots?clustering=dbscan")
        data = r.json()
        clusters = data.get("hotspots", {}).get("location", [])
        
        print(f"Found {len(clusters)} clusters.\n")
        
        for i, c in enumerate(clusters):
            # Pick a representative name (most common)
            loc_name = "Unknown"
            if c.get("locations"):
                # locations is a list in JSON
                loc_name = c["locations"][0]
            
            print(f"CLUSTER #{i+1}: {loc_name}")
            print(f"  - Events: {c['count']}")
            print(f"  - Center: {c.get('center_lat', 0):.2f}, {c.get('center_lng', 0):.2f}")
            
            # Print Sources
            sources = c.get("top_sources", [])
            if sources:
                print("  - TOP SOURCES:")
                for src in sources:
                    # src is [url, count] list from Counter.most_common
                    url = src[0]
                    count = src[1]
                    print(f"    * {url} ({count} refs)")
            print("-" * 80)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print_dbscan_clusters()
