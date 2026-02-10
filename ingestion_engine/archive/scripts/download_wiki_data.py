#!/usr/bin/env python3
"""
Download comprehensive country data from multiple open sources.
Generates data/country_info.json with maximized static information.

Data sources:
- GitHub datasets/country-codes (ISO codes, capitals, languages, etc.)
- Wikidata SPARQL (area, coordinates, neighbors, flag emoji, time zones, etc.)
- Curated data for religions and cultural information
"""

import json
import csv
import urllib.request
import urllib.parse
import os
from io import StringIO

# URLs for data sources
COUNTRY_CODES_URL = "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Wikidata SPARQL query for comprehensive country data
WIKIDATA_COUNTRY_QUERY = """
SELECT DISTINCT ?country ?countryLabel ?iso3 ?area ?lat ?lon ?flagEmoji ?anthem ?anthemLabel 
       ?capital ?capitalLabel ?independence ?landlocked ?unescoCount ?timezone ?nationalAnimal ?nationalAnimalLabel
WHERE {
  ?country wdt:P31 wd:Q6256.  # Instance of country
  
  OPTIONAL { ?country wdt:P298 ?iso3. }  # ISO 3166-1 alpha-3
  OPTIONAL { ?country wdt:P2046 ?area. }  # Area
  OPTIONAL { 
    ?country p:P625 ?coordStatement.
    ?coordStatement ps:P625 ?coord.
    BIND(geof:latitude(?coord) AS ?lat)
    BIND(geof:longitude(?coord) AS ?lon)
  }
  OPTIONAL { ?country wdt:P41 ?flag. }  # Flag image
  OPTIONAL { ?country wdt:P487 ?flagEmoji. }  # Flag emoji (Unicode)
  OPTIONAL { ?country wdt:P85 ?anthem. }  # National anthem
  OPTIONAL { ?country wdt:P36 ?capital. }  # Capital
  OPTIONAL { ?country wdt:P571 ?independence. }  # Inception/Independence
  OPTIONAL { ?country wdt:P610 ?highestPoint. }  # Highest point exists = not landlocked indicator
  
  # UNESCO World Heritage count (subquery)
  OPTIONAL {
    SELECT ?country (COUNT(DISTINCT ?heritage) AS ?unescoCount) WHERE {
      ?heritage wdt:P17 ?country;
                wdt:P1435 wd:Q9259.  # World Heritage Site
    } GROUP BY ?country
  }
  
  OPTIONAL { ?country wdt:P421 ?tz. ?tz rdfs:label ?timezone. FILTER(LANG(?timezone) = "en") }
  OPTIONAL { ?country wdt:P1451 ?nationalAnimal. }  # National animal
  
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

# Simplified query for neighbors (separate to avoid timeout)
WIKIDATA_NEIGHBORS_QUERY = """
SELECT ?country ?iso3 (GROUP_CONCAT(DISTINCT ?neighborISO; SEPARATOR=",") AS ?neighbors)
WHERE {
  ?country wdt:P31 wd:Q6256;
           wdt:P298 ?iso3;
           wdt:P47 ?neighbor.
  ?neighbor wdt:P298 ?neighborISO.
}
GROUP BY ?country ?iso3
"""

# ISO 3166-2 subdivisions query
WIKIDATA_SUBDIVISIONS_QUERY = """
SELECT ?country ?countryISO3 ?subdivision ?subdivisionLabel ?subdivisionCode ?subdivisionType ?subdivisionTypeLabel ?capital ?capitalLabel
WHERE {
  ?country wdt:P31 wd:Q6256;
           wdt:P298 ?countryISO3.
  
  ?subdivision wdt:P17 ?country;
               wdt:P31/wdt:P279* wd:Q10864048.  # First-level administrative division
  
  OPTIONAL { ?subdivision wdt:P300 ?subdivisionCode. }  # ISO 3166-2 code
  OPTIONAL { ?subdivision wdt:P31 ?subdivisionType. }  # Type (state, province, etc.)
  OPTIONAL { ?subdivision wdt:P36 ?capital. }  # Capital
  
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 10000
"""

# Curated religion data (from Wikipedia - major religions by percentage)
RELIGION_DATA = {
    "IND": {"Hindu": 79.8, "Muslim": 14.2, "Christian": 2.3, "Sikh": 1.7},
    "CHN": {"Unaffiliated": 52, "Folk": 21, "Buddhist": 18, "Christian": 5},
    "USA": {"Christian": 65, "Unaffiliated": 26, "Jewish": 2, "Muslim": 1},
    "IDN": {"Muslim": 87, "Christian": 10, "Hindu": 1.7},
    "PAK": {"Muslim": 96, "Hindu": 2, "Christian": 1.6},
    "NGA": {"Muslim": 50, "Christian": 48},
    "BRA": {"Christian": 88, "Unaffiliated": 8},
    "BGD": {"Muslim": 90, "Hindu": 8},
    "RUS": {"Christian": 71, "Unaffiliated": 25},
    "MEX": {"Christian": 90, "Unaffiliated": 7},
    "JPN": {"Shinto": 70, "Buddhist": 67, "Christian": 1.5},
    "DEU": {"Christian": 53, "Unaffiliated": 42, "Muslim": 5},
    "GBR": {"Christian": 46, "Unaffiliated": 37, "Muslim": 6},
    "FRA": {"Christian": 51, "Unaffiliated": 40, "Muslim": 8},
    "ITA": {"Christian": 80, "Unaffiliated": 16},
    "THA": {"Buddhist": 93, "Muslim": 5},
    "KOR": {"Unaffiliated": 56, "Christian": 28, "Buddhist": 16},
    "SAU": {"Muslim": 93, "Christian": 4},
    "CAN": {"Christian": 67, "Unaffiliated": 24, "Muslim": 3},
    "AUS": {"Christian": 52, "Unaffiliated": 30, "Buddhist": 2.4},
    "ESP": {"Christian": 69, "Unaffiliated": 27},
    "TUR": {"Muslim": 98, "Unaffiliated": 2},
    "IRN": {"Muslim": 99.5},
    "EGY": {"Muslim": 90, "Christian": 10},
    "ZAF": {"Christian": 80, "Unaffiliated": 15},
    "ARG": {"Christian": 79, "Unaffiliated": 18},
    "COL": {"Christian": 92, "Unaffiliated": 7},
    "PHL": {"Christian": 92, "Muslim": 5},
    "VNM": {"Unaffiliated": 73, "Buddhist": 16, "Christian": 8},
    "MYS": {"Muslim": 61, "Buddhist": 20, "Christian": 9, "Hindu": 6},
    "NPL": {"Hindu": 81, "Buddhist": 9, "Muslim": 4},
    "ISR": {"Jewish": 74, "Muslim": 18, "Christian": 2},
    "GRC": {"Christian": 90, "Muslim": 2, "Unaffiliated": 4},
    "POL": {"Christian": 87, "Unaffiliated": 10},
    "NLD": {"Unaffiliated": 51, "Christian": 44, "Muslim": 5},
    "PRT": {"Christian": 81, "Unaffiliated": 15},
    "SWE": {"Unaffiliated": 52, "Christian": 42},
}

# Territorial disputes - curated data showing in both claimant countries
TERRITORIAL_DISPUTES = {
    "kashmir": {
        "region": "Kashmir",
        "description": "Disputed territory in the Himalayas, divided between India, Pakistan, and China since 1947",
        "claimants": ["IND", "PAK", "CHN"],
        "status": "Divided administration",
        "type": "territorial",
        "since": 1947
    },
    "crimea": {
        "region": "Crimea",
        "description": "Peninsula annexed by Russia from Ukraine in 2014, internationally recognized as Ukrainian",
        "claimants": ["UKR", "RUS"],
        "status": "Russian administration, claimed by Ukraine",
        "type": "territorial",
        "since": 2014
    },
    "taiwan": {
        "region": "Taiwan",
        "description": "Self-governing island claimed by PRC, with its own government since 1949",
        "claimants": ["CHN", "TWN"],
        "status": "De facto independent",
        "type": "sovereignty",
        "since": 1949
    },
    "south_china_sea": {
        "region": "South China Sea",
        "description": "Maritime disputes over islands and resources between multiple nations",
        "claimants": ["CHN", "VNM", "PHL", "MYS", "BRN", "TWN"],
        "status": "Multiple overlapping claims",
        "type": "maritime",
        "since": 1947
    },
    "golan_heights": {
        "region": "Golan Heights",
        "description": "Territory captured by Israel from Syria in 1967, annexed in 1981",
        "claimants": ["ISR", "SYR"],
        "status": "Israeli administration",
        "type": "territorial",
        "since": 1967
    },
    "western_sahara": {
        "region": "Western Sahara",
        "description": "Former Spanish colony, disputed between Morocco and Sahrawi Arab Democratic Republic",
        "claimants": ["MAR", "ESH"],
        "status": "Mostly Moroccan administration",
        "type": "sovereignty",
        "since": 1975
    },
    "falklands": {
        "region": "Falkland Islands (Malvinas)",
        "description": "British Overseas Territory in South Atlantic, claimed by Argentina",
        "claimants": ["GBR", "ARG"],
        "status": "British administration",
        "type": "sovereignty",
        "since": 1833
    },
    "kuril_islands": {
        "region": "Kuril Islands (Northern Territories)",
        "description": "Islands held by Russia, claimed by Japan since WWII",
        "claimants": ["RUS", "JPN"],
        "status": "Russian administration",
        "type": "territorial",
        "since": 1945
    },
    "arunachal": {
        "region": "Arunachal Pradesh (South Tibet)",
        "description": "Indian state claimed by China as South Tibet",
        "claimants": ["IND", "CHN"],
        "status": "Indian administration",
        "type": "territorial",
        "since": 1962
    },
    "aksai_chin": {
        "region": "Aksai Chin",
        "description": "Region administered by China, claimed by India as part of Ladakh",
        "claimants": ["CHN", "IND"],
        "status": "Chinese administration",
        "type": "territorial",
        "since": 1962
    },
    "gaza": {
        "region": "Gaza Strip",
        "description": "Coastal territory with disputed sovereignty between Israel and Palestine",
        "claimants": ["ISR", "PSE"],
        "status": "Disputed",
        "type": "territorial",
        "since": 1967
    },
    "west_bank": {
        "region": "West Bank",
        "description": "Territory with Israeli settlements, claimed by Palestine",
        "claimants": ["ISR", "PSE"],
        "status": "Partially occupied",
        "type": "territorial",
        "since": 1967
    },
    "cyprus": {
        "region": "Northern Cyprus",
        "description": "Territory occupied by Turkey since 1974, recognized only by Turkey",
        "claimants": ["CYP", "TUR"],
        "status": "Turkish administration",
        "type": "territorial",
        "since": 1974
    },
    "dokdo": {
        "region": "Dokdo/Takeshima",
        "description": "Small islands in Sea of Japan disputed between Korea and Japan",
        "claimants": ["KOR", "JPN"],
        "status": "Korean administration",
        "type": "territorial",
        "since": 1952
    },
    "senkaku": {
        "region": "Senkaku/Diaoyu Islands",
        "description": "Islands in East China Sea administered by Japan, claimed by China and Taiwan",
        "claimants": ["JPN", "CHN", "TWN"],
        "status": "Japanese administration",
        "type": "territorial",
        "since": 1972
    },
    "abkhazia": {
        "region": "Abkhazia",
        "description": "Breakaway region from Georgia with Russian support",
        "claimants": ["GEO", "RUS"],
        "status": "De facto independent, limited recognition",
        "type": "sovereignty",
        "since": 2008
    },
    "south_ossetia": {
        "region": "South Ossetia",
        "description": "Breakaway region from Georgia with Russian support",
        "claimants": ["GEO", "RUS"],
        "status": "De facto independent, limited recognition",
        "type": "sovereignty",
        "since": 2008
    },
    "transnistria": {
        "region": "Transnistria",
        "description": "Breakaway region from Moldova with Russian support",
        "claimants": ["MDA", "RUS"],
        "status": "De facto independent, unrecognized",
        "type": "sovereignty",
        "since": 1992
    },
    "nagorno_karabakh": {
        "region": "Nagorno-Karabakh",
        "description": "Region in Azerbaijan, formerly disputed with Armenia",
        "claimants": ["AZE", "ARM"],
        "status": "Azerbaijani control since 2023",
        "type": "territorial",
        "since": 1991
    },
}

# Currency symbols mapping
CURRENCY_SYMBOLS = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CNY": "¥", "CHF": "Fr", "AUD": "$", "CAD": "$", "NZD": "$",
    "RUB": "₽", "KRW": "₩", "BRL": "R$", "MXN": "$", "ZAR": "R",
    "THB": "฿", "SGD": "$", "HKD": "$", "SEK": "kr", "NOK": "kr",
    "DKK": "kr", "PLN": "zł", "TRY": "₺", "AED": "د.إ", "SAR": "﷼",
    "ILS": "₪", "PHP": "₱", "IDR": "Rp", "MYR": "RM", "PKR": "₨",
    "BDT": "৳", "NGN": "₦", "EGP": "£", "VND": "₫", "CLP": "$",
    "COP": "$", "ARS": "$", "PEN": "S/", "UAH": "₴", "CZK": "Kč",
}

# Continent code to full name
CONTINENT_NAMES = {
    "AF": "Africa", "AN": "Antarctica", "AS": "Asia",
    "EU": "Europe", "NA": "North America", "OC": "Oceania", "SA": "South America",
}

# Language code to readable name
LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French",
    "de": "German", "it": "Italian", "pt": "Portuguese", "ru": "Russian",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
    "bn": "Bengali", "te": "Telugu", "mr": "Marathi", "ta": "Tamil",
    "ur": "Urdu", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "nl": "Dutch", "pl": "Polish", "tr": "Turkish",
    "vi": "Vietnamese", "th": "Thai", "id": "Indonesian", "ms": "Malay",
    "sw": "Swahili", "he": "Hebrew", "el": "Greek", "cs": "Czech",
    "hu": "Hungarian", "sv": "Swedish", "da": "Danish", "no": "Norwegian",
    "fi": "Finnish", "uk": "Ukrainian", "ro": "Romanian", "bg": "Bulgarian",
    "hr": "Croatian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian",
    "fa": "Persian", "ne": "Nepali", "si": "Sinhala", "my": "Burmese",
    "km": "Khmer", "lo": "Lao", "am": "Amharic", "cy": "Welsh",
    "gd": "Scottish Gaelic", "ga": "Irish", "haw": "Hawaiian",
}

# Flag emoji mapping (ISO3 -> emoji)
FLAG_EMOJI = {
    "AFG": "🇦🇫", "ALB": "🇦🇱", "DZA": "🇩🇿", "AND": "🇦🇩", "AGO": "🇦🇴",
    "ARG": "🇦🇷", "ARM": "🇦🇲", "AUS": "🇦🇺", "AUT": "🇦🇹", "AZE": "🇦🇿",
    "BHS": "🇧🇸", "BHR": "🇧🇭", "BGD": "🇧🇩", "BRB": "🇧🇧", "BLR": "🇧🇾",
    "BEL": "🇧🇪", "BLZ": "🇧🇿", "BEN": "🇧🇯", "BTN": "🇧🇹", "BOL": "🇧🇴",
    "BIH": "🇧🇦", "BWA": "🇧🇼", "BRA": "🇧🇷", "BRN": "🇧🇳", "BGR": "🇧🇬",
    "BFA": "🇧🇫", "BDI": "🇧🇮", "KHM": "🇰🇭", "CMR": "🇨🇲", "CAN": "🇨🇦",
    "CPV": "🇨🇻", "CAF": "🇨🇫", "TCD": "🇹🇩", "CHL": "🇨🇱", "CHN": "🇨🇳",
    "COL": "🇨🇴", "COM": "🇰🇲", "COG": "🇨🇬", "COD": "🇨🇩", "CRI": "🇨🇷",
    "CIV": "🇨🇮", "HRV": "🇭🇷", "CUB": "🇨🇺", "CYP": "🇨🇾", "CZE": "🇨🇿",
    "DNK": "🇩🇰", "DJI": "🇩🇯", "DMA": "🇩🇲", "DOM": "🇩🇴", "ECU": "🇪🇨",
    "EGY": "🇪🇬", "SLV": "🇸🇻", "GNQ": "🇬🇶", "ERI": "🇪🇷", "EST": "🇪🇪",
    "ETH": "🇪🇹", "FJI": "🇫🇯", "FIN": "🇫🇮", "FRA": "🇫🇷", "GAB": "🇬🇦",
    "GMB": "🇬🇲", "GEO": "🇬🇪", "DEU": "🇩🇪", "GHA": "🇬🇭", "GRC": "🇬🇷",
    "GRD": "🇬🇩", "GTM": "🇬🇹", "GIN": "🇬🇳", "GNB": "🇬🇼", "GUY": "🇬🇾",
    "HTI": "🇭🇹", "HND": "🇭🇳", "HUN": "🇭🇺", "ISL": "🇮🇸", "IND": "🇮🇳",
    "IDN": "🇮🇩", "IRN": "🇮🇷", "IRQ": "🇮🇶", "IRL": "🇮🇪", "ISR": "🇮🇱",
    "ITA": "🇮🇹", "JAM": "🇯🇲", "JPN": "🇯🇵", "JOR": "🇯🇴", "KAZ": "🇰🇿",
    "KEN": "🇰🇪", "KIR": "🇰🇮", "PRK": "🇰🇵", "KOR": "🇰🇷", "KWT": "🇰🇼",
    "KGZ": "🇰🇬", "LAO": "🇱🇦", "LVA": "🇱🇻", "LBN": "🇱🇧", "LSO": "🇱🇸",
    "LBR": "🇱🇷", "LBY": "🇱🇾", "LIE": "🇱🇮", "LTU": "🇱🇹", "LUX": "🇱🇺",
    "MKD": "🇲🇰", "MDG": "🇲🇬", "MWI": "🇲🇼", "MYS": "🇲🇾", "MDV": "🇲🇻",
    "MLI": "🇲🇱", "MLT": "🇲🇹", "MHL": "🇲🇭", "MRT": "🇲🇷", "MUS": "🇲🇺",
    "MEX": "🇲🇽", "FSM": "🇫🇲", "MDA": "🇲🇩", "MCO": "🇲🇨", "MNG": "🇲🇳",
    "MNE": "🇲🇪", "MAR": "🇲🇦", "MOZ": "🇲🇿", "MMR": "🇲🇲", "NAM": "🇳🇦",
    "NRU": "🇳🇷", "NPL": "🇳🇵", "NLD": "🇳🇱", "NZL": "🇳🇿", "NIC": "🇳🇮",
    "NER": "🇳🇪", "NGA": "🇳🇬", "NOR": "🇳🇴", "OMN": "🇴🇲", "PAK": "🇵🇰",
    "PLW": "🇵🇼", "PAN": "🇵🇦", "PNG": "🇵🇬", "PRY": "🇵🇾", "PER": "🇵🇪",
    "PHL": "🇵🇭", "POL": "🇵🇱", "PRT": "🇵🇹", "QAT": "🇶🇦", "ROU": "🇷🇴",
    "RUS": "🇷🇺", "RWA": "🇷🇼", "KNA": "🇰🇳", "LCA": "🇱🇨", "VCT": "🇻🇨",
    "WSM": "🇼🇸", "SMR": "🇸🇲", "STP": "🇸🇹", "SAU": "🇸🇦", "SEN": "🇸🇳",
    "SRB": "🇷🇸", "SYC": "🇸🇨", "SLE": "🇸🇱", "SGP": "🇸🇬", "SVK": "🇸🇰",
    "SVN": "🇸🇮", "SLB": "🇸🇧", "SOM": "🇸🇴", "ZAF": "🇿🇦", "SSD": "🇸🇸",
    "ESP": "🇪🇸", "LKA": "🇱🇰", "SDN": "🇸🇩", "SUR": "🇸🇷", "SWZ": "🇸🇿",
    "SWE": "🇸🇪", "CHE": "🇨🇭", "SYR": "🇸🇾", "TWN": "🇹🇼", "TJK": "🇹🇯",
    "TZA": "🇹🇿", "THA": "🇹🇭", "TLS": "🇹🇱", "TGO": "🇹🇬", "TON": "🇹🇴",
    "TTO": "🇹🇹", "TUN": "🇹🇳", "TUR": "🇹🇷", "TKM": "🇹🇲", "TUV": "🇹🇻",
    "UGA": "🇺🇬", "UKR": "🇺🇦", "ARE": "🇦🇪", "GBR": "🇬🇧", "USA": "🇺🇸",
    "URY": "🇺🇾", "UZB": "🇺🇿", "VUT": "🇻🇺", "VAT": "🇻🇦", "VEN": "🇻🇪",
    "VNM": "🇻🇳", "YEM": "🇾🇪", "ZMB": "🇿🇲", "ZWE": "🇿🇼", "PSE": "🇵🇸",
    "GRL": "🇬🇱", "PRI": "🇵🇷", "HKG": "🇭🇰", "MAC": "🇲🇴",
}

# Curated additional data (national animals, dishes, etc.)
NATIONAL_DATA = {
    "IND": {"national_animal": "Bengal Tiger", "national_bird": "Indian Peafowl", "national_flower": "Lotus"},
    "USA": {"national_animal": "Bald Eagle", "national_bird": "Bald Eagle", "national_flower": "Rose"},
    "GBR": {"national_animal": "Lion", "national_flower": "Tudor Rose"},
    "CHN": {"national_animal": "Giant Panda", "national_flower": "Plum Blossom"},
    "AUS": {"national_animal": "Red Kangaroo", "national_bird": "Emu", "national_flower": "Golden Wattle"},
    "CAN": {"national_animal": "Beaver", "national_flower": "Sugar Maple"},
    "BRA": {"national_animal": "Jaguar", "national_flower": "Golden Trumpet"},
    "RUS": {"national_animal": "Brown Bear", "national_flower": "Chamomile"},
    "JPN": {"national_animal": "Green Pheasant", "national_flower": "Cherry Blossom"},
    "DEU": {"national_animal": "Federal Eagle", "national_flower": "Cornflower"},
    "FRA": {"national_animal": "Gallic Rooster", "national_flower": "Lily"},
    "ITA": {"national_animal": "Italian Wolf", "national_flower": "Lily"},
    "MEX": {"national_animal": "Golden Eagle", "national_flower": "Dahlia"},
    "ZAF": {"national_animal": "Springbok", "national_bird": "Blue Crane", "national_flower": "King Protea"},
    "NZL": {"national_animal": "Kiwi", "national_flower": "Kowhai"},
    "KOR": {"national_animal": "Siberian Tiger", "national_flower": "Hibiscus"},
    "ESP": {"national_animal": "Bull", "national_flower": "Red Carnation"},
    "ARG": {"national_animal": "Rufous Hornero", "national_flower": "Ceibo"},
    "THA": {"national_animal": "Thai Elephant", "national_flower": "Ratchaphruek"},
    "EGY": {"national_animal": "Steppe Eagle", "national_flower": "Egyptian Lotus"},
    "KEN": {"national_animal": "Lion", "national_flower": "Orchid"},
    "NGA": {"national_animal": "Eagle", "national_flower": "Costus"},
    "PAK": {"national_animal": "Markhor", "national_flower": "Jasmine"},
    "BGD": {"national_animal": "Royal Bengal Tiger", "national_flower": "White Water Lily"},
    "IDN": {"national_animal": "Komodo Dragon", "national_flower": "Moon Orchid"},
    "PHL": {"national_animal": "Carabao", "national_flower": "Sampaguita"},
    "VNM": {"national_animal": "Water Buffalo", "national_flower": "Lotus"},
    "TUR": {"national_animal": "Grey Wolf", "national_flower": "Tulip"},
    "IRN": {"national_animal": "Asiatic Lion", "national_flower": "Red Rose"},
    "SAU": {"national_animal": "Arabian Camel", "national_flower": "Rose"},
}


def download_csv(url):
    """Download CSV data from URL and return as list of dicts."""
    print(f"Downloading from {url}...")
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read().decode('utf-8')
            reader = csv.DictReader(StringIO(content))
            return list(reader)
    except Exception as e:
        print(f"Error downloading CSV: {e}")
        return []


def query_wikidata(query):
    """Execute a SPARQL query against Wikidata and return results."""
    try:
        url = WIKIDATA_SPARQL_URL + "?" + urllib.parse.urlencode({
            "query": query,
            "format": "json"
        })
        req = urllib.request.Request(url, headers={
            "User-Agent": "WikiDataBot/1.0 (https://github.com/example; example@example.com)",
            "Accept": "application/sparql-results+json"
        })
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Wikidata query error: {e}")
        return None


def parse_languages(lang_str):
    """Parse languages from CSV and convert ISO codes to readable names."""
    if not lang_str:
        return []
    
    raw_codes = [l.strip() for l in lang_str.split(',') if l.strip()]
    readable = []
    seen = set()
    
    for code in raw_codes:
        base = code.split('-')[0].lower()
        if base in seen:
            continue
        seen.add(base)
        name = LANGUAGE_NAMES.get(base, base.upper())
        readable.append(name)
    
    return readable[:5]


def get_driving_side(code):
    """Return driving side for a country."""
    left_drivers = {
        "GBR", "AUS", "IND", "JPN", "ZAF", "THA", "IDN", "MYS", "SGP",
        "HKG", "NZL", "IRL", "PAK", "BGD", "LKA", "KEN", "TZA", "UGA",
        "ZWE", "BWA", "NAM", "MOZ", "ZMB", "MWI", "JAM", "TTO", "BRB",
        "BHS", "CYP", "MLT", "MUS", "NPL", "BTN"
    }
    return "left" if code in left_drivers else "right"


def get_neighbors_data():
    """Fetch neighboring countries data from Wikidata."""
    print("Fetching neighbor data from Wikidata...")
    result = query_wikidata(WIKIDATA_NEIGHBORS_QUERY)
    
    neighbors = {}
    if result and 'results' in result:
        for binding in result['results']['bindings']:
            iso3 = binding.get('iso3', {}).get('value', '')
            neighbor_list = binding.get('neighbors', {}).get('value', '')
            if iso3 and neighbor_list:
                neighbors[iso3] = [n.strip() for n in neighbor_list.split(',') if n.strip()]
    
    return neighbors


def main():
    print("=== Comprehensive Country Data Downloader ===\n")
    
    # Download main dataset
    raw_data = download_csv(COUNTRY_CODES_URL)
    if not raw_data:
        print("Failed to download country data")
        return
    
    print(f"Downloaded {len(raw_data)} country entries\n")
    
    # Fetch neighbor data from Wikidata
    neighbors_data = get_neighbors_data()
    print(f"Got neighbor data for {len(neighbors_data)} countries\n")
    
    # Process into our format
    country_info = {}
    
    for row in raw_data:
        iso3 = row.get('ISO3166-1-Alpha-3', '').strip()
        iso2 = row.get('ISO3166-1-Alpha-2', '').strip()
        if not iso3:
            continue
        
        # Basic info
        name = row.get('official_name_en') or row.get('CLDR display name') or row.get('name', '')
        capital = row.get('Capital', '')
        continent = row.get('Continent', '')
        region = row.get('Region Name', '')
        
        # Currency
        currency_code = row.get('ISO4217-currency_alphabetic_code', '')
        currency_name = row.get('ISO4217-currency_name', '')
        
        # Languages
        languages_str = row.get('Languages', '')
        languages = parse_languages(languages_str)
        
        # Contact info
        calling_code = row.get('Dial', '')
        if calling_code and not calling_code.startswith('+'):
            calling_code = '+' + calling_code
        
        tld = row.get('TLD', '')
        
        # Convert continent code
        continent_name = CONTINENT_NAMES.get(continent, continent) if continent else None
        
        # Build entry
        entry = {
            "name": name,
            "iso2": iso2 if iso2 else None,
            "capital": capital if capital else None,
            "continent": continent_name,
            "region": region if region else None,
            "languages": languages if languages else None,
            "calling_code": calling_code if calling_code else None,
            "tld": tld if tld else None,
            "driving_side": get_driving_side(iso3),
            "flag_emoji": FLAG_EMOJI.get(iso3),
        }
        
        # Add currency
        if currency_code:
            symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
            entry["currency"] = {
                "name": currency_name,
                "code": currency_code,
                "symbol": symbol
            }
        
        # Add neighbors
        if iso3 in neighbors_data:
            entry["neighbors"] = neighbors_data[iso3]
        
        # Add religion data
        if iso3 in RELIGION_DATA:
            entry["religions"] = RELIGION_DATA[iso3]
        
        # Add national symbols
        if iso3 in NATIONAL_DATA:
            entry.update(NATIONAL_DATA[iso3])
        
        # Add territorial disputes (show in all claimant countries)
        disputes = []
        for dispute_key, dispute_data in TERRITORIAL_DISPUTES.items():
            if iso3 in dispute_data["claimants"]:
                # Get other claimant names
                other_claimants = [c for c in dispute_data["claimants"] if c != iso3]
                disputes.append({
                    "region": dispute_data["region"],
                    "description": dispute_data["description"],
                    "other_claimants": other_claimants,
                    "status": dispute_data["status"],
                    "type": dispute_data["type"],
                    "since": dispute_data["since"]
                })
        if disputes:
            entry["disputes"] = disputes
        
        # Remove None values
        entry = {k: v for k, v in entry.items() if v is not None}
        
        country_info[iso3] = entry
    
    # Ensure output directory exists
    os.makedirs('data', exist_ok=True)
    
    # Write to JSON file
    output_path = 'data/country_info.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(country_info, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Generated {output_path} with {len(country_info)} countries")
    
    # Print sample
    print("\n=== Sample Entry (India) ===")
    if 'IND' in country_info:
        print(json.dumps(country_info['IND'], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
