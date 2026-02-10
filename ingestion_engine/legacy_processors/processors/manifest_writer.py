import json
import os
from datetime import datetime
from pathlib import Path

from ingestion_engine.legacy_processors.processors.geocoder import Geocoder
from ingestion_engine.legacy_processors.processors.deduplicator import Deduplicator

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / 'data'
INTERACTIONS_DIR = DATA_DIR / 'interactions'
MANIFEST_FILE = INTERACTIONS_DIR / 'manifest.json'

CATEGORY_FALLBACKS = {
    "disputes": ["territorial", "sovereignty", "maritime", "political", "trade", "diplomatic", "resource", "ethnic", "war", "border_crisis"],
    "meetings": ["summit", "bilateral", "multilateral", "state_visit", "politburo", "g7", "g20", "un", "asean", "nato", "eu", "brics"],
    "agreements": ["treaty", "trade_deal", "defense_pact", "ceasefire", "peace_accord", "mou", "fta", "extradition"],
    "sports": ["olympics", "world_cup", "commonwealth", "asian_games", "friendly", "championship", "cricket", "formula1"],
    "trade": ["sanction", "tariff", "embargo", "investment", "aid", "loan", "currency"],
    "military": ["exercise", "deployment", "alliance", "arms_deal", "incident", "patrol"],
    "humanitarian": ["disaster_relief", "refugee", "medical", "food_aid", "evacuation"],
    "cultural": ["exchange", "festival", "education", "tourism", "heritage"],
    "other": []
}

def load_manifest():
    if not MANIFEST_FILE.exists():
        return {"version": "3.0", "categories": {}, "byCategory": {}, "interactionsById": {}}
    with open(MANIFEST_FILE, 'r') as f:
        return json.load(f)

def save_manifest(manifest):
    manifest['last_updated'] = datetime.utcnow().isoformat() + 'Z'
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2)


def slugify(text):
    import re
    slug = text.lower()
    slug = re.sub(r'[/\\\\]', '_', slug)
    slug = re.sub(r'[^a-z0-9_]', '_', slug)
    slug = re.sub(r'_+', '_', slug)
    return slug.strip('_')


def ensure_categories(manifest):
    if 'categories' not in manifest:
        manifest['categories'] = {}
    for cat, subtypes in CATEGORY_FALLBACKS.items():
        if cat not in manifest['categories']:
            manifest['categories'][cat] = {
                "name": cat.title(),
                "icon": "🌐" if cat == "other" else "",
                "color": "#9ca3af",
                "subtypes": subtypes
            }
    if 'byCategory' not in manifest or not isinstance(manifest.get('byCategory'), dict):
        manifest['byCategory'] = {}
    if 'interactionsById' not in manifest or not isinstance(manifest.get('interactionsById'), dict):
        manifest['interactionsById'] = {}
    for cat in manifest['categories'].keys():
        if cat not in manifest['byCategory']:
            manifest['byCategory'][cat] = []


def ensure_category_entry(manifest, category: str):
    category = (category or "other").lower()
    if 'categories' not in manifest:
        manifest['categories'] = {}
    if category not in manifest['categories']:
        manifest['categories'][category] = {
            "name": category.replace('_', ' ').title(),
            "icon": "",
            "color": "#9ca3af",
            "subtypes": []
        }
    if 'byCategory' not in manifest or not isinstance(manifest.get('byCategory'), dict):
        manifest['byCategory'] = {}
    if category not in manifest['byCategory']:
        manifest['byCategory'][category] = []


def _upgrade_manifest_to_v3_if_needed(manifest: dict) -> dict:
    if isinstance(manifest, dict) and isinstance(manifest.get("interactionsById"), dict) and isinstance(manifest.get("byCategory"), dict):
        if not manifest.get("version"):
            manifest["version"] = "3.0"
        return manifest

    categories = manifest.get("categories") or {}
    interactions = manifest.get("interactions") or {}
    out = {
        "version": "3.0",
        "last_updated": manifest.get("last_updated"),
        "categories": categories,
        "byCategory": {},
        "interactionsById": {},
    }

    seen = set()
    for cat, entries in interactions.items():
        if not isinstance(entries, list):
            continue
        out["byCategory"].setdefault(cat, [])
        for e in entries:
            if not isinstance(e, dict):
                continue
            iid = e.get("id")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            subtype = (e.get("subtype") or e.get("type") or "general").lower()
            cat_name = (categories.get(cat) or {}).get("name") or str(cat).title()
            type_label = f"{cat_name} · {subtype}".strip() if subtype and subtype != "general" else cat_name
            entry = {**e}
            entry.pop("llm_analysis", None)
            entry["category"] = (e.get("category") or cat).lower()
            entry["subtype"] = subtype
            entry["type"] = entry.get("type_label") or type_label
            entry["type_label"] = entry["type"]
            entry["short_description"] = entry.get("short_description") or entry.get("description") or ""
            entry["description"] = entry.get("description") or entry["short_description"]
            out["interactionsById"][iid] = entry
            out["byCategory"][cat].append(iid)

    return out

def process_new_events(raw_events):
    manifest = _upgrade_manifest_to_v3_if_needed(load_manifest())
    ensure_categories(manifest)
    by_category = manifest.get('byCategory', {})
    interactions_by_id = manifest.get('interactionsById', {})
    
    geo = Geocoder()
    dedup = Deduplicator(manifest)
    
    added_count = 0
    category_counts = {}
    
    for event in raw_events:
        if 'participants_iso' not in event:
            event = geo.process_event(event)
        participants_iso = event.get('participants_iso') or event.get('participants') or []
        if not participants_iso and event.get('visualization_type') != 'dot':
            print(f"Skipping {event.get('name')}: No valid participants identified")
            continue
        event['participants_iso'] = list(participants_iso) if isinstance(participants_iso, list) else [participants_iso]

        category = (event.get('category') or 'other').lower()
        ensure_category_entry(manifest, category)
        by_category.setdefault(category, [])

        # Subtype is the within-category classifier.
        subtype = (event.get('subtype') or 'general').lower()
        valid_subtypes = (manifest.get('categories', {}).get(category, {}) or {}).get('subtypes', [])
        if valid_subtypes and subtype not in valid_subtypes:
            subtype = 'general'

        new_id = dedup.generate_id(event)
        if new_id in interactions_by_id:
            print(f"Skipping duplicate: {new_id}")
            continue

        cat_name = (manifest.get("categories", {}).get(category, {}) or {}).get("name") or category.title()
        type_label = f"{cat_name} · {subtype}" if subtype and subtype != "general" else cat_name

        entry = {
            "id": new_id,
            "name": event['name'],
            "category": category,
            "subtype": subtype,
            "type": type_label,
            "status": event.get('status', 'Active'),
            "participants": event['participants_iso'],
            "short_description": event.get('description', ''),
            "description": event.get('description', ''),
            "file": f"{category}/{new_id}.json",
            "date": event.get('date'),
            "visualization_type": event.get('visualization_type', 'geodesic'),
            "arc_style": event.get('arc_style', 'solid'),
            "location": event.get('location'),
            "toast_message": event.get('toast_message', ''),
            "toast_type": event.get('toast_type', 'info'),
            "llm_analysis_cached": bool(event.get('llm_analysis_cached')) or bool(event.get('llm_analysis')),
            "confidence": event.get('confidence'),
            "source": event.get('source', 'llm'),
            "type_label": type_label,
        }
        
        if dedup.is_duplicate(entry):
            print(f"Skipping duplicate: {entry['id']}")
            continue

        source_urls = event.get('source_urls') or ([event.get('source_url')] if event.get('source_url') else [])
        sources = [{"url": u, "type": "article", "name": "Source"} for u in source_urls if u]
        entry["sources"] = sources

        detail_dir = INTERACTIONS_DIR / category
        detail_dir.mkdir(parents=True, exist_ok=True)
        detail_payload = {
            "id": entry['id'],
            "name": entry['name'],
            "category": category,
            "subtype": subtype,
            "type": entry['type'],
            "type_label": type_label,
            "status": entry['status'],
            "participants": entry['participants'],
            "description": event.get('description', ''),
            "sources": sources,
            "date": entry.get('date'),
            "topology": event.get('topology', 'mesh'),
            "hub": event.get('hub'),
            "visualization_type": entry['visualization_type'],
            "arc_style": entry['arc_style'],
            "location": entry.get('location'),
            "toast_message": entry.get('toast_message', ''),
            "toast_type": entry.get('toast_type', 'info'),
            "llm_analysis": event.get('llm_analysis') or "",
            "llm_analysis_cached": entry.get('llm_analysis_cached', False),
            "confidence": entry.get('confidence'),
            "source": entry.get('source', 'llm'),
            "source_urls": source_urls,
            "gdelt_metadata": event.get("gdelt_metadata"),
        }
        with open(detail_dir / f"{new_id}.json", 'w') as f:
            json.dump(detail_payload, f, indent=2)

        interactions_by_id[new_id] = entry
        by_category[category].append(new_id)
        added_count += 1
        print(f"Added: {entry['name']} ({category})")
        category_counts[category] = category_counts.get(category, 0) + 1
        
    manifest['byCategory'] = by_category
    manifest['interactionsById'] = interactions_by_id
    save_manifest(manifest)
    print(f"Successfully added {added_count} new events.")
    if category_counts:
        summary = ", ".join(f"{k}={v}" for k, v in sorted(category_counts.items(), key=lambda x: (-x[1], x[0])))
        print(f"Category counts: {summary}")

def main():
    # Example usage - reading from stdin or file
    # For now, we'll just demonstrate with a dummy call if run directly
    pass

if __name__ == '__main__':
    # Simulating data passed from LLM collector
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        with open(input_file, 'r') as f:
            data = json.load(f)
            if 'events' in data:
                process_new_events(data['events'])
