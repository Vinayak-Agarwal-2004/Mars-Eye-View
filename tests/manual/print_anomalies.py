
import requests
import json

BASE_URL = "http://localhost:8000/api"

def print_all_anomalies():
    print(f"Fetching ALL anomalies (Sigma > 2.0) from {BASE_URL}...\n")
    try:
        # Fetch data
        r = requests.get(f"{BASE_URL}/anomalies?lookback_days=7&sigma=2.0")
        data = r.json()
        anoms = data.get("anomalies", [])
        
        # Sort by Z-score (most extreme first)
        anoms.sort(key=lambda x: x["z_score"], reverse=True)
        
        print(f"Found {len(anoms)} anomalies.\n")
        print(f"{'LOCATION':<50} | {'SEVERITY':<10} | {'Z-SCORE':<8} | {'EVENTS (Today/Avg)':<20}")
        print("-" * 100)
        
        for a in anoms:
            loc = (a['location'][:47] + '..') if len(a['location']) > 47 else a['location']
            counts = f"{a['current_count']} / {a['baseline_mean']:.1f}"
            print(f"{loc:<50} | {a['severity']:<10} | {a['z_score']:<8.2f} | {counts:<20}")
            
            # Print Sources
            sources = a.get("top_sources", [])
            if sources:
                print("   SOURCES:")
                for src in sources:
                    print(f"   - {src['url']} ({src['count']} refs)")
            print("-" * 100)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print_all_anomalies()
