#!/usr/bin/env python3
"""
Download FULL RESOLUTION ADM1 and ADM2 GeoJSON data from geoBoundaries.
(Not simplified - these are the accurate, high-quality boundaries)
"""

import json
import subprocess
import os

def download_with_curl(url, dest):
    """Use curl to download (handles GitHub LFS redirects properly)"""
    try:
        result = subprocess.run(
            ['curl', '-sL', '-o', dest, url],
            capture_output=True,
            timeout=180
        )
        if result.returncode == 0 and os.path.exists(dest):
            size = os.path.getsize(dest)
            with open(dest, 'r') as f:
                first_char = f.read(1)
            if first_char == '{':
                return size
            else:
                os.remove(dest)
                return 0
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 0


def main():
    print("Fetching metadata from geoBoundaries API...")
    import urllib.request
    
    adm1_api = "https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM1/"
    adm2_api = "https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM2/"
    
    with urllib.request.urlopen(adm1_api, timeout=60) as resp:
        adm1_list = json.loads(resp.read().decode('utf-8'))
    print(f"Got {len(adm1_list)} ADM1 entries")
    
    with urllib.request.urlopen(adm2_api, timeout=60) as resp:
        adm2_list = json.loads(resp.read().decode('utf-8'))
    print(f"Got {len(adm2_list)} ADM2 entries")
    
    os.makedirs('data/adm1', exist_ok=True)
    os.makedirs('data/adm2', exist_ok=True)
    
    sources = {}
    
    # Download FULL RESOLUTION ADM1 (not simplified!)
    print(f"\n=== Downloading ADM1 (FULL RESOLUTION) ===")
    total = len(adm1_list)
    downloaded = 0
    total_size = 0
    
    for i, item in enumerate(adm1_list):
        iso = item.get('boundaryISO')
        if not iso:
            continue
        
        # Use FULL resolution GeoJSON URL (gjDownloadURL), not simplified
        gj_url = item.get('gjDownloadURL')
        if not gj_url:
            continue
        
        name = item.get('boundaryName', iso)
        dest = f"data/adm1/{iso}.geojson"
        
        # Skip if already exists and is reasonably sized (>100KB means full resolution)
        if os.path.exists(dest) and os.path.getsize(dest) > 100000:
            print(f"  [{i+1}/{total}] {iso}: Already exists (full res)")
            sources[iso] = {'name': name, 'adm1': dest, 'adm2': None}
            continue
        
        size = download_with_curl(gj_url, dest)
        if size > 0:
            downloaded += 1
            total_size += size
            print(f"  [{i+1}/{total}] {iso}: {size/1024/1024:.2f} MB")
            sources[iso] = {'name': name, 'adm1': dest, 'adm2': None}
        else:
            print(f"  [{i+1}/{total}] {iso}: FAILED")
    
    print(f"\nADM1: Downloaded {downloaded} files, {total_size/1024/1024/1024:.2f} GB total")
    
    # Download FULL RESOLUTION ADM2
    print(f"\n=== Downloading ADM2 (FULL RESOLUTION) ===")
    total = len(adm2_list)
    downloaded = 0
    adm2_size = 0
    
    for i, item in enumerate(adm2_list):
        iso = item.get('boundaryISO')
        if not iso:
            continue
        
        # Use FULL resolution GeoJSON URL
        gj_url = item.get('gjDownloadURL')
        if not gj_url:
            continue
        
        dest = f"data/adm2/{iso}.geojson"
        
        # Skip if already exists and is reasonably sized
        if os.path.exists(dest) and os.path.getsize(dest) > 100000:
            print(f"  [{i+1}/{total}] {iso}: Already exists (full res)")
            if iso in sources:
                sources[iso]['adm2'] = dest
            continue
        
        size = download_with_curl(gj_url, dest)
        if size > 0:
            downloaded += 1
            adm2_size += size
            print(f"  [{i+1}/{total}] {iso}: {size/1024/1024:.2f} MB")
            if iso in sources:
                sources[iso]['adm2'] = dest
            else:
                sources[iso] = {'name': iso, 'adm1': None, 'adm2': dest}
        else:
            print(f"  [{i+1}/{total}] {iso}: FAILED")
    
    total_size += adm2_size
    print(f"\nADM2: Downloaded {downloaded} files, {adm2_size/1024/1024/1024:.2f} GB total")
    print(f"\n=== TOTAL: {total_size/1024/1024/1024:.2f} GB ===")
    
    with open('data/country_sources.json', 'w') as f:
        json.dump(sources, f, indent=2)
    
    print(f"\nUpdated data/country_sources.json with {len(sources)} countries")
    print("Done! Refresh the map.")


if __name__ == "__main__":
    main()
