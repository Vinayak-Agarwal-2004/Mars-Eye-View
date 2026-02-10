
import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000/api"

def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def analyze_anomalies():
    print_section("1. ANOMALY DETECTION (Live Data)")
    try:
        r = requests.get(f"{BASE_URL}/anomalies?lookback_days=7&sigma=2.0")
        data = r.json()
        anoms = data.get("anomalies", [])
        
        # RAW DATA GLIMPSE
        print("RAW DATA (First Anomaly JSON):")
        if anoms:
            print(json.dumps(anoms[0], indent=2))
        else:
            print("[]")
        print("-" * 60)
        
        print(f"Found {len(anoms)} anomalies (Sigma > 2.0)\n")
        
        # Sort by Z-score
        anoms.sort(key=lambda x: x["z_score"], reverse=True)
        
        for i, a in enumerate(anoms[:5]):
            print(f"Anomaly #{i+1}: {a['location']}")
            print(f"  - Severity: {a['severity'].upper()}")
            print(f"  - Z-Score:  {a['z_score']} (Normal is 0.0)")
            print(f"  - Counts:   {a['current_count']} events today (Baseline Avg: {a['baseline_mean']})")
            print(f"  - Spike:    {a['percent_above_normal']}% above normal")
            print("-" * 40)
            
        print("\n--> ANALYSIS:")
        if anoms:
            top = anoms[0]
            print(f"The code identified '{top['location']}' as the #1 anomaly.")
            print(f"This means while it usually has ~{top['baseline_mean']} events/day, today it had {top['current_count']}.")
            print(f"A Z-score of {top['z_score']} is statistically extreme.")
        else:
            print("No anomalies found. Operations are within normal baseline levels.")
            
    except Exception as e:
        print(f"Error: {e}")

def analyze_actor_network():
    print_section("2. ACTOR NETWORK (Live Data)")
    try:
        r = requests.get(f"{BASE_URL}/actor-network?min_weight=3")
        data = r.json()
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        # RAW DATA GLIMPSE
        print("RAW DATA (First Node & Edge):")
        if nodes: print("Node:", json.dumps(nodes[0], indent=2))
        if edges: print("Edge:", json.dumps(edges[0], indent=2))
        print("-" * 60)
        
        print(f"Analyzed {data['summary']['total_actors']} actors.")
        print(f"Found {len(edges)} significant relationships (min_weight=3).\n")
        
        print("Top 5 Key Actors (by volume):")
        # Sort nodes by count
        nodes.sort(key=lambda x: x["count"], reverse=True)
        for n in nodes[:5]:
            print(f"  - {n['id'].ljust(20)} : {n['count']} events (Primary Role: {n['primary_role']})")
            
        print("\nTop 5 Strongest Relationships (Edges):")
        for e in edges[:5]:
            print(f"  - {e['source']} <--> {e['target']} : {e['weight']} interactions")
            
        print("\n--> ANALYSIS:")
        if edges:
            top_edge = edges[0]
            print(f"The strongest link is between '{top_edge['source']}' and '{top_edge['target']}'.")
            print("This indicates they are frequently mentioned together in the same news stories.")
            print("The code effectively filtered out thousands of one-off mentions to find these recurring pairs.")

    except Exception as e:
        print(f"Error: {e}")

def analyze_dbscan():
    print_section("3. DBSCAN CLUSTERING (Live Data)")
    try:
        r = requests.get(f"{BASE_URL}/hotspots?clustering=dbscan")
        data = r.json()
        clusters = data.get("hotspots", {}).get("location", [])
        
        # RAW DATA GLIMPSE
        print("RAW DATA (First Cluster):")
        if clusters:
            # Print without the huge list of locations for readability
            c_copy = clusters[0].copy()
            c_copy['locations'] = list(c_copy['locations'])[:5] + ["..."] if c_copy.get('locations') else []
            print(json.dumps(c_copy, indent=2))
        else:
            print("[]")
        print("-" * 60)
        
        print(f"DBSCAN found {len(clusters)} geographic clusters (vs hundreds of grid cells).\n")
        
        for i, c in enumerate(clusters[:5]):
            lat = c.get('center_lat', 0)
            lng = c.get('center_lng', 0)
            locs = c.get('locations', [])
            top_loc = locs[0] if locs else "Unknown"
            
            print(f"Cluster #{i+1}: {top_loc} (approx)")
            print(f"  - Events:   {c['count']}")
            print(f"  - Center:   {lat:.2f}, {lng:.2f}")
            print(f"  - Includes: {', '.join(locs[:3])}...")
            print("-" * 40)
            
        print("\n--> ANALYSIS:")
        if clusters:
            c1 = clusters[0]
            print(f"Cluster #1 grouped {c1['count']} events around {c1.get('center_lat',0):.2f}, {c1.get('center_lng',0):.2f}.")
            print(f"Unlike a grid, this cluster formed naturally based on event density.")
            print(f"It likely captured a specific conflict zone or metropolitan area regardless of borders.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_anomalies()
    analyze_actor_network()
    analyze_dbscan()
