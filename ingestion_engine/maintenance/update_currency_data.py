#!/usr/bin/env python3
"""
Fetch currency exchange rates relative to INR using Frankfurter API (Free, ECB data).

USAGE (CRON - Every 12 hours):
1.  Open crontab: `crontab -e`
2.  Add line: `0 */12 * * * /usr/bin/python3 /path/to/ingestion_engine/maintenance/update_currency_data.py`
"""

import requests
import json
import os
from datetime import datetime

OUTPUT_FILE = 'data/currency_rates.json'

def main():
    print("Fetching currency rates from Frankfurter API (Base: INR)...")
    
    # 1. Primary Source: Frankfurter (High Accuracy, ~30 Major Currencies)
    url_prim = "https://api.frankfurter.dev/v1/latest?base=INR"
    # 2. Secondary Source: fawazahmed0 (High Coverage, ~200+ Currencies/Metals/Crypto)
    url_sec = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/inr.json"
    
    inr_rates = {} # Stores: 1 Foreign Unit = X INR

    # --- Fetch Secondary (Broad Coverage) ---
    try:
        print(f"Fetching secondary data from {url_sec}...")
        resp = requests.get(url_sec, timeout=30)
        data_sec = resp.json()
        
        # Structure: {"date": "...", "inr": {"usd": 0.012, "eur": 0.011, ...}}
        # API returns: 1 INR = X Foreign
        if 'inr' in data_sec:
            for curr, rate_inr_base in data_sec['inr'].items():
                if rate_inr_base != 0:
                    curr_code = curr.upper()
                    inr_rates[curr_code] = 1 / rate_inr_base
            print(f" > Loaded {len(inr_rates)} rates from secondary source.")
    except Exception as e:
        print(f" ! Secondary source failed: {e}")

    # --- Fetch Primary (High Reliability) & Overwrite ---
    try:
        print(f"Fetching primary data from {url_prim}...")
        resp = requests.get(url_prim, timeout=30)
        data_prim = resp.json()

        # Structure: {"rates": {"USD": 0.012, ...}}
        # API returns: 1 INR = X Foreign
        if 'rates' in data_prim:
            count = 0
            for curr, rate_inr_base in data_prim['rates'].items():
                if rate_inr_base != 0:
                    curr_code = curr.upper()
                    inr_rates[curr_code] = 1 / rate_inr_base
                    count += 1
            print(f" > Overwrote/Added {count} rates from primary source (Frankfurter).")
            
            # Use primary date for metadata if available
            date_str = data_prim.get('date', datetime.now().strftime("%Y-%m-%d"))
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
    except Exception as e:
        print(f" ! Primary source failed: {e}")
        # If primary fails but secondary worked, we still have data.
        if not inr_rates:
            return

    inr_rates['INR'] = 1.0 # Base case

    # Structure for frontend
    output = {
        "base": "Foreign",
        "target": "INR",
        "date": date_str if 'date_str' in locals() else datetime.now().strftime("%Y-%m-%d"),
        "last_updated": datetime.now().isoformat(),
        "rates": inr_rates
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
        
    print(f"Success! Saved {len(output['rates'])} rates to {OUTPUT_FILE}")
    print(f"Sample: 1 USD = {output['rates'].get('USD', 0):.2f} INR")



if __name__ == "__main__":
    main()
