import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Try to import feedparser, provide helpful error if missing
try:
    import feedparser
except ImportError:
    print("Error: 'feedparser' module not found. Please install it using: pip install feedparser")
    sys.exit(1)

# Configuration
FEEDS = {
    'reuters_world': 'http://feeds.reuters.com/reuters/worldNews',
    'bbc_world': 'http://feeds.bbci.co.uk/news/world/rss.xml',
    'aljazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
    'un_news': 'https://news.un.org/feed/subscribe/en/news/all/rss.xml'
}

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / 'data'
OUTPUT_FILE = DATA_DIR / 'interactions' / 'raw_rss_events.json'

def load_keywords():
    """Load country names and capitals for filtering."""
    keywords = set()
    
    # Load countries
    try:
        with open(DATA_DIR / 'country_info.json', 'r') as f:
            countries = json.load(f)
            for iso, info in countries.items():
                keywords.add(info['name'].lower())
                # Add alternate names if available (simple implementation)
    except Exception as e:
        print(f"Warning: Could not load country info: {e}")

    # Load capitals
    try:
        with open(DATA_DIR / 'capitals.json', 'r') as f:
            capitals = json.load(f)
            # capitals.json uses a dict: {"countries": {ISO: {name, lat, lng}}, "states": {...}}
            for cap in (capitals.get('countries') or {}).values():
                name = cap.get('name') if isinstance(cap, dict) else None
                if name:
                    keywords.add(name.lower())
            for state_caps in (capitals.get('states') or {}).values():
                if isinstance(state_caps, dict):
                    for cap in state_caps.values():
                        if isinstance(cap, dict):
                            name = cap.get('name')
                            if name:
                                keywords.add(name.lower())
    except Exception as e:
        print(f"Warning: Could not load capitals: {e}")
        
    return keywords

def has_geocodable_reference(text, keywords):
    """Check if text contains at least one known country or capital."""
    if not text:
        return False
    
    text_lower = text.lower()
    for kw in keywords:
        # Simple substring match - in production interactions this should be stricter (regex/NER)
        # to avoid matching 'march' (month) vs 'March' (city/name) etc.
        # But for now, we rely on the keyword set being mostly distinct names
        if f" {kw} " in f" {text_lower} ":  # basic boundary check
            return True
    return False

def collect_feeds():
    """Fetch and filter RSS feeds."""
    keywords = load_keywords()
    print(f"Loaded {len(keywords)} geolocation keywords for filtering.")
    
    collected_events = []
    
    for source, url in FEEDS.items():
        print(f"Fetching {source}...")
        try:
            feed = feedparser.parse(url)
            print(f"  Found {len(feed.entries)} entries")
            
            for entry in feed.entries:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                published = entry.get('published', datetime.now().isoformat())
                link = entry.get('link', '')
                
                # Combine title and summary for keyword checking
                full_text = f"{title} {summary}"
                
                if has_geocodable_reference(full_text, keywords):
                    collected_events.append({
                        'source': source,
                        'source_type': 'rss',
                        'title': title,
                        'description': summary,
                        'url': link,
                        'date': published,
                        'raw_text': full_text,
                        'status': 'unprocessed'
                    })
        except Exception as e:
            print(f"  Error fetching {source}: {e}")
            
    print(f"Collected {len(collected_events)} geographically relevant events.")
    
    # Save to file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(collected_events, f, indent=2)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    collect_feeds()
