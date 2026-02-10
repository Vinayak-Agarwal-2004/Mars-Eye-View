#!/usr/bin/env python3
"""
Fetch high-quality latitude/longitude data for Global Capitals and State Capitals.
Strategy: Wikidata Iterative (Per Country) to avoid Timeouts.
"""

import requests
import json
import os
import time
import sys

OUTPUT_FILE = 'data/capitals.json'
SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    'User-Agent': 'AntigravityBot/1.0 (paansingh@example.com)',
    'Accept': 'application/sparql-results+json'
}

def query_sparql(q):
    try:
        resp = requests.get(SPARQL_URL, params={'query': q, 'format': 'json'}, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            print("   ! Rate limit. Waiting 5s...")
            time.sleep(5)
            return query_sparql(q)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"   ! Request failed: {e}")
        return None

def fetch_countries():
    print("Fetching Country List (ISO3 + QID)...")
    q = """
    SELECT ?country ?countryCode ?capitalLabel ?coord WHERE {
      ?country wdt:P31 wd:Q6256 .
      ?country wdt:P298 ?countryCode . # ISO Alpha-3
      ?country wdt:P36 ?capital .
      ?capital wdt:P625 ?coord .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    """
    data = query_sparql(q)
    countries = {}
    country_list = []
    
    if data:
        for item in data['results']['bindings']:
            try:
                iso = item['countryCode']['value']
                qid = item['country']['value'].split('/')[-1]
                name = item['capitalLabel']['value']
                wkt = item['coord']['value']
                lng, lat = wkt.replace('Point(', '').replace(')', '').split(' ')
                
                countries[iso] = {"lat": float(lat), "lng": float(lng), "name": name}
                country_list.append({'iso': iso, 'qid': qid})
            except: continue
            
    print(f" > Found {len(countries)} countries.")
    return countries, country_list

def fetch_states_for_country(country_qid):
    # Query for First Level Admin Divisions of this specific country
    q = f"""
    SELECT ?adminLabel ?capitalLabel ?coord WHERE {{
      ?admin wdt:P31/wdt:P279* wd:Q10864048 .
      ?admin wdt:P17 wd:{country_qid} .
      ?admin wdt:P36 ?capital .
      ?capital wdt:P625 ?coord .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 500
    """
    data = query_sparql(q)
    states = {}
    if data:
        for item in data['results']['bindings']:
            try:
                name = item['adminLabel']['value']
                cap_name = item['capitalLabel']['value']
                wkt = item['coord']['value']
                lng, lat = wkt.replace('Point(', '').replace(')', '').split(' ')
                # Simple normalization to avoid duplicates if multiple types match
                if name not in states:
                    states[name] = {"lat": float(lat), "lng": float(lng), "name": cap_name}
            except: continue
    return states

def main():
    countries, country_list = fetch_countries()
    
    if not countries:
        print("Failed to fetch initial country data.")
        sys.exit(1)
        
    all_states = {} # iso3 -> {name -> data}
    
    print(f"Fetching states for {len(country_list)} countries (Iterative)...")
    
    count_s = 0
    # Prioritize major countries for user experience if partial fail, but we try all.
    # We can create a 'priority' list if needed, but let's just run.
    
    print(f"Fetching states for {len(country_list)} countries (Parallel)...")
    
    import concurrent.futures
    
    all_states = {} # iso3 -> {name -> data}
    count_s = 0
    
    # Function for thread worker
    def process_country(c):
        iso = c['iso']
        qid = c['qid']
        s_data = fetch_states_for_country(qid)
        return iso, s_data

    # Use ThreadPool
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_iso = {executor.submit(process_country, c): c['iso'] for c in country_list}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_iso)):
            iso = future_to_iso[future]
            try:
                c_iso, states = future.result()
                if states:
                    all_states[c_iso] = states
                    count_s += len(states)
            except Exception as exc:
                print(f"   ! {iso} generated an exception: {exc}")
            
            if i % 20 == 0:
                 print(f" > [{i}/{len(country_list)}] Processed...")

    print(f"Done! Parsed {count_s} state capitals across {len(all_states)} countries.")
    
    output = {
        "countries": countries,
        "states": all_states
    }
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
