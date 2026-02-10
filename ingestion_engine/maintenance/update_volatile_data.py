#!/usr/bin/env python3
"""
Update volatile country data that changes frequently.
Run this script periodically (weekly/monthly) to refresh dynamic data.

Data sources:
- REST Countries API (population)
- World Bank API (GDP, economic indicators)
- Wikidata (current leaders)

Generates data/volatile_data.json with timestamps.
"""

import json
import urllib.request
import os
from datetime import datetime, timezone

# API URLs
REST_COUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=cca3,population,area,gini"
WORLD_BANK_GDP_URL = "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=300&date=2022"
WORLD_BANK_GDP_PC_URL = "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD?format=json&per_page=300&date=2022"

# Curated current leaders (updated manually - this changes with elections)
# Last updated: February 2026
CURRENT_LEADERS = {
    "IND": {"head_of_state": "Droupadi Murmu", "head_of_government": "Narendra Modi", "title_hos": "President", "title_hog": "Prime Minister"},
    "USA": {"head_of_state": "Donald Trump", "head_of_government": "Donald Trump", "title_hos": "President", "title_hog": "President"},
    "CHN": {"head_of_state": "Xi Jinping", "head_of_government": "Li Qiang", "title_hos": "President", "title_hog": "Premier"},
    "GBR": {"head_of_state": "Charles III", "head_of_government": "Keir Starmer", "title_hos": "Monarch", "title_hog": "Prime Minister"},
    "FRA": {"head_of_state": "Emmanuel Macron", "head_of_government": "Michel Barnier", "title_hos": "President", "title_hog": "Prime Minister"},
    "DEU": {"head_of_state": "Frank-Walter Steinmeier", "head_of_government": "Olaf Scholz", "title_hos": "President", "title_hog": "Chancellor"},
    "JPN": {"head_of_state": "Naruhito", "head_of_government": "Shigeru Ishiba", "title_hos": "Emperor", "title_hog": "Prime Minister"},
    "RUS": {"head_of_state": "Vladimir Putin", "head_of_government": "Mikhail Mishustin", "title_hos": "President", "title_hog": "Prime Minister"},
    "BRA": {"head_of_state": "Luiz Inácio Lula da Silva", "head_of_government": "Luiz Inácio Lula da Silva", "title_hos": "President", "title_hog": "President"},
    "CAN": {"head_of_state": "Charles III", "head_of_government": "Justin Trudeau", "title_hos": "Monarch", "title_hog": "Prime Minister"},
    "AUS": {"head_of_state": "Charles III", "head_of_government": "Anthony Albanese", "title_hos": "Monarch", "title_hog": "Prime Minister"},
    "MEX": {"head_of_state": "Claudia Sheinbaum", "head_of_government": "Claudia Sheinbaum", "title_hos": "President", "title_hog": "President"},
    "KOR": {"head_of_state": "Yoon Suk-yeol", "head_of_government": "Han Duck-soo", "title_hos": "President", "title_hog": "Prime Minister"},
    "ITA": {"head_of_state": "Sergio Mattarella", "head_of_government": "Giorgia Meloni", "title_hos": "President", "title_hog": "Prime Minister"},
    "ESP": {"head_of_state": "Felipe VI", "head_of_government": "Pedro Sánchez", "title_hos": "King", "title_hog": "Prime Minister"},
    "IDN": {"head_of_state": "Prabowo Subianto", "head_of_government": "Prabowo Subianto", "title_hos": "President", "title_hog": "President"},
    "TUR": {"head_of_state": "Recep Tayyip Erdoğan", "head_of_government": "Recep Tayyip Erdoğan", "title_hos": "President", "title_hog": "President"},
    "SAU": {"head_of_state": "Salman bin Abdulaziz", "head_of_government": "Mohammed bin Salman", "title_hos": "King", "title_hog": "Crown Prince/PM"},
    "ARG": {"head_of_state": "Javier Milei", "head_of_government": "Javier Milei", "title_hos": "President", "title_hog": "President"},
    "ZAF": {"head_of_state": "Cyril Ramaphosa", "head_of_government": "Cyril Ramaphosa", "title_hos": "President", "title_hog": "President"},
    "EGY": {"head_of_state": "Abdel Fattah el-Sisi", "head_of_government": "Mostafa Madbouly", "title_hos": "President", "title_hog": "Prime Minister"},
    "PAK": {"head_of_state": "Asif Ali Zardari", "head_of_government": "Shehbaz Sharif", "title_hos": "President", "title_hog": "Prime Minister"},
    "NGA": {"head_of_state": "Bola Tinubu", "head_of_government": "Bola Tinubu", "title_hos": "President", "title_hog": "President"},
    "BGD": {"head_of_state": "Mohammed Shahabuddin", "head_of_government": "Sheikh Hasina", "title_hos": "President", "title_hog": "Prime Minister"},
    "VNM": {"head_of_state": "Tô Lâm", "head_of_government": "Phạm Minh Chính", "title_hos": "President", "title_hog": "Prime Minister"},
    "PHL": {"head_of_state": "Bongbong Marcos", "head_of_government": "Bongbong Marcos", "title_hos": "President", "title_hog": "President"},
    "THA": {"head_of_state": "Rama X", "head_of_government": "Paetongtarn Shinawatra", "title_hos": "King", "title_hog": "Prime Minister"},
    "MYS": {"head_of_state": "Ibrahim Iskandar", "head_of_government": "Anwar Ibrahim", "title_hos": "King", "title_hog": "Prime Minister"},
    "POL": {"head_of_state": "Andrzej Duda", "head_of_government": "Donald Tusk", "title_hos": "President", "title_hog": "Prime Minister"},
    "NLD": {"head_of_state": "Willem-Alexander", "head_of_government": "Dick Schoof", "title_hos": "King", "title_hog": "Prime Minister"},
    "UKR": {"head_of_state": "Volodymyr Zelenskyy", "head_of_government": "Denys Shmyhal", "title_hos": "President", "title_hog": "Prime Minister"},
    "ISR": {"head_of_state": "Isaac Herzog", "head_of_government": "Benjamin Netanyahu", "title_hos": "President", "title_hog": "Prime Minister"},
    "IRN": {"head_of_state": "Ali Khamenei", "head_of_government": "Masoud Pezeshkian", "title_hos": "Supreme Leader", "title_hog": "President"},
    "NZL": {"head_of_state": "Charles III", "head_of_government": "Christopher Luxon", "title_hos": "Monarch", "title_hog": "Prime Minister"},
    "SGP": {"head_of_state": "Tharman Shanmugaratnam", "head_of_government": "Lawrence Wong", "title_hos": "President", "title_hog": "Prime Minister"},
    "CHE": {"head_of_state": "Karin Keller-Sutter", "head_of_government": "Federal Council", "title_hos": "President", "title_hog": "Federal Council"},
    "SWE": {"head_of_state": "Carl XVI Gustaf", "head_of_government": "Ulf Kristersson", "title_hos": "King", "title_hog": "Prime Minister"},
    "NOR": {"head_of_state": "Harald V", "head_of_government": "Jonas Gahr Støre", "title_hos": "King", "title_hog": "Prime Minister"},
    "DNK": {"head_of_state": "Frederik X", "head_of_government": "Mette Frederiksen", "title_hos": "King", "title_hog": "Prime Minister"},
    "FIN": {"head_of_state": "Alexander Stubb", "head_of_government": "Petteri Orpo", "title_hos": "President", "title_hog": "Prime Minister"},
    "AUT": {"head_of_state": "Alexander Van der Bellen", "head_of_government": "Karl Nehammer", "title_hos": "President", "title_hog": "Chancellor"},
    "BEL": {"head_of_state": "Philippe", "head_of_government": "Alexander De Croo", "title_hos": "King", "title_hog": "Prime Minister"},
    "GRC": {"head_of_state": "Katerina Sakellaropoulou", "head_of_government": "Kyriakos Mitsotakis", "title_hos": "President", "title_hog": "Prime Minister"},
    "PRT": {"head_of_state": "Marcelo Rebelo de Sousa", "head_of_government": "Luís Montenegro", "title_hos": "President", "title_hog": "Prime Minister"},
    "CZE": {"head_of_state": "Petr Pavel", "head_of_government": "Petr Fiala", "title_hos": "President", "title_hog": "Prime Minister"},
    "IRL": {"head_of_state": "Michael D. Higgins", "head_of_government": "Simon Harris", "title_hos": "President", "title_hog": "Taoiseach"},
    "COL": {"head_of_state": "Gustavo Petro", "head_of_government": "Gustavo Petro", "title_hos": "President", "title_hog": "President"},
    "CHL": {"head_of_state": "Gabriel Boric", "head_of_government": "Gabriel Boric", "title_hos": "President", "title_hog": "President"},
    "PER": {"head_of_state": "Dina Boluarte", "head_of_government": "Dina Boluarte", "title_hos": "President", "title_hog": "President"},
    "KEN": {"head_of_state": "William Ruto", "head_of_government": "William Ruto", "title_hos": "President", "title_hog": "President"},
}


def fetch_json(url):
    """Fetch JSON from URL with error handling."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "VolatileDataBot/1.0"
        })
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def format_number(n):
    """Format large numbers for display."""
    if n is None:
        return None
    if n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.2f}T"
    elif n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(int(n))


def main():
    print("=== Volatile Data Updater ===\n")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
    
    volatile_data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "data_sources": {
            "population": "REST Countries API",
            "gdp": "World Bank (2022)",
            "leaders": "Curated (Feb 2026)"
        },
        "countries": {}
    }
    
    # Fetch population and area from REST Countries
    print("Fetching population data from REST Countries...")
    rest_data = fetch_json(REST_COUNTRIES_URL)
    
    population_data = {}
    area_data = {}
    
    if rest_data:
        for country in rest_data:
            iso3 = country.get('cca3')
            if iso3:
                population_data[iso3] = country.get('population')
                area_data[iso3] = country.get('area')
        print(f"Got population for {len(population_data)} countries")
    else:
        print("Failed to fetch REST Countries data")
    
    # Fetch GDP from World Bank
    print("\nFetching GDP data from World Bank...")
    gdp_data = {}
    gdp_response = fetch_json(WORLD_BANK_GDP_URL)
    
    if gdp_response and len(gdp_response) > 1:
        for entry in gdp_response[1]:
            if entry and entry.get('value'):
                iso3 = entry.get('countryiso3code')
                if iso3:
                    gdp_data[iso3] = entry['value']
        print(f"Got GDP for {len(gdp_data)} countries")
    else:
        print("Failed to fetch World Bank GDP data")
    
    # Fetch GDP per capita
    print("\nFetching GDP per capita from World Bank...")
    gdp_pc_data = {}
    gdp_pc_response = fetch_json(WORLD_BANK_GDP_PC_URL)
    
    if gdp_pc_response and len(gdp_pc_response) > 1:
        for entry in gdp_pc_response[1]:
            if entry and entry.get('value'):
                iso3 = entry.get('countryiso3code')
                if iso3:
                    gdp_pc_data[iso3] = entry['value']
        print(f"Got GDP per capita for {len(gdp_pc_data)} countries")
    
    # Combine all data
    print("\nCombining data...")
    
    # Get all unique ISO3 codes
    all_codes = set(population_data.keys()) | set(gdp_data.keys()) | set(CURRENT_LEADERS.keys())
    
    for iso3 in all_codes:
        entry = {}
        
        # Population
        if iso3 in population_data and population_data[iso3]:
            entry["population"] = population_data[iso3]
            entry["population_formatted"] = format_number(population_data[iso3])
        
        # Area
        if iso3 in area_data and area_data[iso3]:
            entry["area_km2"] = area_data[iso3]
            entry["area_formatted"] = format_number(area_data[iso3]) + " km²"
        
        # GDP
        if iso3 in gdp_data and gdp_data[iso3]:
            entry["gdp_usd"] = gdp_data[iso3]
            entry["gdp_formatted"] = "$" + format_number(gdp_data[iso3])
        
        # GDP per capita
        if iso3 in gdp_pc_data and gdp_pc_data[iso3]:
            entry["gdp_per_capita"] = round(gdp_pc_data[iso3])
            entry["gdp_per_capita_formatted"] = f"${int(gdp_pc_data[iso3]):,}"
        
        # Leaders
        if iso3 in CURRENT_LEADERS:
            entry["leaders"] = CURRENT_LEADERS[iso3]
        
        if entry:
            volatile_data["countries"][iso3] = entry
    
    # Write output
    os.makedirs('data', exist_ok=True)
    output_path = 'data/volatile_data.json'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(volatile_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Generated {output_path} with {len(volatile_data['countries'])} countries")
    
    # Sample output
    print("\n=== Sample Entry (India) ===")
    if 'IND' in volatile_data['countries']:
        print(json.dumps(volatile_data['countries']['IND'], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
