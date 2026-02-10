import requests
import zipfile
import io
import csv
import sys

# Fix Bug 1: Increase CSV field size limit for large GKG fields
csv.field_size_limit(10 * 1024 * 1024)  # 10MB limit

import json
import os
import sys
from datetime import datetime, timedelta

try:
    from taxonomy import GDELT_MAPPING, COLORS
except ModuleNotFoundError:
    from ingestion_engine.streamers.taxonomy import GDELT_MAPPING, COLORS

# Configuration
LAST_UPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "live", "gdelt_latest.json")

def get_latest_urls():
    """Fetch the latest export.CSV.zip AND gkg.CSV.zip URLs."""
    urls = {}
    try:
        print("Checking for updates...")
        resp = requests.get(LAST_UPDATE_URL, timeout=10)
        resp.raise_for_status()
        
        # print(f"DEBUG UPDATE LIST: {resp.text[:200]}") # Optional debug
        
        for line in resp.text.splitlines():
            parts = line.split(" ")
            if len(parts) >= 3:
                url = parts[2]
                url_lower = url.lower()
                if "export.csv.zip" in url_lower:
                    urls['export'] = url
                elif "gkg.csv.zip" in url_lower:
                    urls['gkg'] = url
                elif "mentions.csv.zip" in url_lower:
                    urls['mentions'] = url
        return urls
    except Exception as e:
        print(f"Error fetching update list: {e}")
        return {}

def parse_gkg_row(row):
    """Parse a GKG row to extract events from V2Locations and V2Themes."""
    features = []
    try:
        if len(row) < 9: return []
        
        date_str = row[1]
        counts_field = row[6]
        # themes_field = row[7] # Unused for now
        # locs_field = row[8]   # Unused for now
        source_name = row[4]
        if not source_name: return [] # Drop "ghost" reports without a publisher
        
        # 1. Process V2Counts (High confidence numeric events)
        if counts_field:
            # Format: CountType#Count#ObjectType#LocType#LocName#Country#ADM1##Lat#Long#...
            for entry in counts_field.split(';'):
                parts = entry.split('#')
                if len(parts) < 10: continue
                
                ctype = parts[0] # KILL, WOUND, ARREST, PROTEST, etc.
                count = parts[1]
                lat = parts[8]
                lng = parts[9]
                
                if not lat or not lng: continue
                
                # Map CountType to Category
                category = None
                if ctype in ['KILL', 'WOUND', 'DEATH']: category = "CONFLICT" 
                elif ctype == 'ARREST': category = "CRIME"
                elif ctype == 'PROTEST': category = "PROTEST"
                elif ctype in ['DISPLACED', 'REFUGEES', 'EVACUATION']: category = "DISPLACEMENT"
                elif ctype == 'KIDNAP': category = "CRIME"
                
                if category:
                    feat = {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                        "properties": {
                            "category": category,
                            "name": f"{category}: {count} {parts[2] or 'people'}", # ObjectType
                            "date": date_str,
                            "color": COLORS.get(category, '#808080'),
                            "source": source_name,
                            "html": f"<b>{category}</b><br>Count: {count}<br>Type: {ctype}<br>Source: {source_name}"
                        }
                    }
                    features.append(feat)
        return features
    except Exception as e:
        return []

def process_stream(url, file_type='export'):
    print(f"Downloading {file_type} stream: {url}...")
    try:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        csv_filename = z.namelist()[0]
        print(f"Parsing {csv_filename}...")
        
        features = []
        with z.open(csv_filename) as f:
            text_stream = io.TextIOWrapper(f, encoding='utf-8', errors='replace')
            reader = csv.reader(text_stream, delimiter='\t')
            
            for row in reader:
                if file_type == 'export':
                    # ... Existing logic ...
                    feat = parse_export_row(row)
                    if feat: features.append(feat)
                elif file_type == 'gkg':
                    # Parse GKG
                    gkg_feats = parse_gkg_row(row)
                    if gkg_feats: features.extend(gkg_feats)
                    
        return features
    except Exception as e:
        print(f"Stream error ({file_type}): {e}")
        return []

def parse_export_row(row):
    try:
        if len(row) < 58: return None
        
        event_code = row[26]
        lat = row[56] # Index 56 is Lat 
        lng = row[57] # Index 57 is Long
        
        if not lat or not lng: return None
        
        try:
            num_mentions = int(float(row[31])) if row[31] else 0
            num_sources = int(float(row[32])) if row[32] else 0
            num_articles = int(float(row[33])) if row[33] else 0
        except:
            num_sources = 0
            num_articles = 0
            
        if num_sources < 1: 
            return None # Drop zero sources
            
        source_url = row[60] if len(row) > 60 else ""
        if not source_url:
            return None # Drop missing source URL
            
        category = GDELT_MAPPING.get(event_code)
        
        if not category:
            if event_code.startswith("19"): category = "CONFLICT"
            elif event_code.startswith("18"): category = "VIOLENCE"
            elif event_code.startswith("14"): category = "PROTEST"
            elif event_code.startswith("17"): category = "CRIME"
            elif event_code.startswith("02"): category = "DISPLACEMENT"
        
        if not category: return None
        
        actor = row[6] or "Unidentified"
        country_name = row[52]
        
        # New: Transnational Filtering Fields
        actor1_country = row[7] if len(row) > 7 else ""
        actor2_country = row[17] if len(row) > 17 else ""
        actiongeo_country = row[51] if len(row) > 51 else ""
        
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
            "properties": {
                "name": f"{category}: {actor}",
                "category": category,
                "date": row[1],
                "countryname": country_name,
                "actor1countrycode": actor1_country,
                "actor2countrycode": actor2_country,
                "actiongeo_countrycode": actiongeo_country,
                "color": COLORS.get(category, '#808080'),
                "importance": num_articles or 1,
                "eventid": row[0],
                "sourceurl": source_url,
                "sources": [{"url": source_url, "type": "article", "name": "GDELT"}]
            }
        }
    except Exception as e:
        return None

def load_existing_data():
    """Load existing features from JSON to enable rolling window."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r') as f:
                data = json.load(f)
                return data.get('features', [])
        except Exception:
            return []
    return []

def prune_old_events(features, hours=24):
    """Refine feature list: Deduplicate, Clean, and Remove old events."""
    valid_features = []
    seen_sigs = set()
    
    current_yyyymmdd = datetime.now().strftime("%Y%m%d")
    yesterday_yyyymmdd = (datetime.now().date() - timedelta(days=1)).strftime("%Y%m%d")
    
    for f in features:
        props = f['properties']
        
        # 0. Reliability Check (Retroactive)
        # Check Source Count
        importance = props.get('importance', 0)
        if importance < 1:
            # GKG counts don't always have 'importance' field set from row[32] 
            # because parse_gkg_row parses counts differently.
            # But GKG counts are inherently "confirmed" by being in the Counts list.
            # We should check if source is "GDELT_EXPORT" vs "GDELT_CSV" (GKG).
            # If source is Export, we must enforce importance.
            if props.get('source') == 'GDELT_EXPORT':
                continue
            # If GKG, we trust it? GKG usually has high confidence.
            # But wait, let's look at `parse_gkg_row`. It sets source name.
            if not props.get('source_name') and not props.get('source'):
                 continue
                 
        # 1. Deduplication Signature - Use event_sig or eventid (Bug 2 fix)
        # Old: name+coords was too aggressive, dropping distinct events at same location
        event_id = props.get('eventid', '')
        fallback_sig = f"{props.get('name')}_{f['geometry']['coordinates']}"
        sig = props.get('event_sig') or f"eid:{event_id}" if event_id else fallback_sig
        if sig in seen_sigs: continue
            
        # 2. Age Pruning
        evt_date = str(props.get('date', ''))
        if len(evt_date) >= 8:
            date_part = evt_date[:8]
            if date_part < yesterday_yyyymmdd:
                continue 
                
        seen_sigs.add(sig)
        valid_features.append(f)
        
    return valid_features


def attach_sources_to_features(features, mention_map):
    """Attach all known source URLs to each feature using the mention map."""
    for feat in features:
        props = feat.get("properties") or {}
        eid = str(props.get("eventid", ""))
        primary = props.get("sourceurl")

        links = set(mention_map.get(eid, set()))
        if primary:
            links.add(primary)

        if links:
            props["sources"] = [
                {"url": u, "type": "article", "name": "GDELT"}
                for u in sorted(links)
            ]
        else:
            props.setdefault("sources", [])

        feat["properties"] = props

    return features

def main():
    urls = get_latest_urls()
    print(f"DEBUG URLS FOUND: {urls.keys()}")
    if not urls: return

    # 1. Fetch Mentions to build URL Map
    mention_map = {}
    if 'mentions' in urls or True: # Force check for mentions based on standard naming
        m_url = urls.get('mentions') or urls['export'].replace('.export.', '.mentions.')
        print(f"Downloading Mentions: {m_url}")
        try:
            r = requests.get(m_url, timeout=30)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            with z.open(z.namelist()[0]) as f:
                content = io.TextIOWrapper(f, encoding='utf-8', errors='replace')
                reader = csv.reader(content, delimiter='\t')
                for row in reader:
                    if len(row) < 6: continue
                    eid = row[0]
                    url = row[5]
                    if eid not in mention_map: mention_map[eid] = set()
                    mention_map[eid].add(url)
        except Exception as e:
            print(f"Mentions fetch failed: {e}")

    new_features = []
    
    # 2. Export (Events)
    if 'export' in urls:
        evts = process_stream(urls['export'], 'export')
        for feat in evts:
            eid = feat.get('properties', {}).get('eventid') # Assuming we add this to parse_export_row
            # Actually, let's fix parse_export_row to include eventid
            pass
        print(f"Export (Events) Yield: {len(evts)}")
        new_features.extend(evts)
        
    # 3. GKG (Counts)
    if 'gkg' in urls:
        gkgs = process_stream(urls['gkg'], 'gkg')
        print(f"GKG (Counts) Yield: {len(gkgs)}")
        new_features.extend(gkgs)

    # 4. Rolling Window Merge
    if new_features:
        print("Merging with existing history and attaching all links...")
        attach_sources_to_features(new_features, mention_map)

        existing_features = load_existing_data()
        print(f"Loaded {len(existing_features)} existing events.")
        
        combined = new_features + existing_features
        final_features = prune_old_events(combined)
        
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        out_data = {"type": "FeatureCollection", "features": final_features}
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(out_data, f, indent=2)
            
        print(f"Saved {len(final_features)} total events (New: {len(new_features)}) to {OUTPUT_FILE}")
    else:
        print("No new features extracted from stream.")

if __name__ == "__main__":
    main()
