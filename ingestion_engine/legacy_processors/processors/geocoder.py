import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / 'data'

class Geocoder:
    def __init__(self):
        self.country_map = {}
        self._load_data()

    def _load_data(self):
        """Load country names and aliases mapped to ISO codes."""
        try:
            with open(DATA_DIR / 'country_info.json', 'r') as f:
                countries = json.load(f)
                for iso, info in countries.items():
                    # Map common name
                    self.country_map[info['name'].lower()] = iso
                    # Map ISO3 code itself
                    self.country_map[iso.lower()] = iso
                    # Map ISO2 if present
                    if info.get('iso2'):
                        self.country_map[info['iso2'].lower()] = iso
                    # Map demonyms if available (simple heuristic for now)
                    # Future: Load a proper alias database
        except Exception as e:
            print(f"Error loading country info: {e}")

        # Add some manual common aliases
        self.country_map.update({
            "us": "USA", "usa": "USA", "united states": "USA", "america": "USA",
            "uk": "GBR", "britain": "GBR", "united kingdom": "GBR",
            "russia": "RUS", "china": "CHN", "india": "IND",
            "south korea": "KOR", "north korea": "PRK",
            "czechia": "CZE", "ivory coast": "CIV", "cote d ivoire": "CIV",
            "laos": "LAO", "bolivia": "BOL", "vietnam": "VNM",
            "syria": "SYR", "iran": "IRN", "myanmar": "MMR"
        })

    def get_iso(self, name):
        """Resolve a country name to its ISO 3166-1 alpha-3 code."""
        if not name:
            return None
        return self.country_map.get(name.strip().lower())

    def process_event(self, event):
        """Enrich event with ISO codes for participants."""
        if 'participants' not in event:
            return event

        isos = []
        for p in event['participants']:
            iso = self.get_iso(p)
            if iso:
                isos.append(iso)
            else:
                print(f"Warning: Could not geocode participant '{p}'")
        
        # Determine valid participants (must have ISO)
        event['participants_iso'] = list(set(isos))
        return event

def main():
    # Simple test
    geo = Geocoder()
    test_event = {
        "participants": ["India", "China", "UnknownLand"]
    }
    processed = geo.process_event(test_event)
    print(f"Processed: {processed['participants_iso']}")

if __name__ == '__main__':
    main()
