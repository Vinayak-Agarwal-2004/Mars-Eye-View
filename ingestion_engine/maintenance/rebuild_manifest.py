import json
import os
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / 'data'
INTERACTIONS_DIR = DATA_DIR / 'interactions'
MANIFEST_PATH = INTERACTIONS_DIR / 'manifest.json'

CATEGORIES = {
    "disputes": {"name": "Disputes", "icon": "⚠️", "color": "#ef4444", "subtypes": ["territorial", "maritime", "political", "border"]},
    "meetings": {"name": "Meetings & Summits", "icon": "🤝", "color": "#3b82f6", "subtypes": ["diplomatic", "summit"]},
    "agreements": {"name": "Agreements & Treaties", "icon": "📜", "color": "#10b981", "subtypes": ["treaty", "normalization"]},
    "sports": {"name": "Sports", "icon": "⚽", "color": "#f59e0b", "subtypes": ["tournament", "match"]},
    "trade": {"name": "Trade & Economics", "icon": "📈", "color": "#8b5cf6", "subtypes": ["deal", "sanctions"]},
    "military": {"name": "Military & Defense", "icon": "🛡️", "color": "#6b7280", "subtypes": ["exercise", "defense_pact"]},
    "humanitarian": {"name": "Humanitarian", "icon": "🩺", "color": "#ec4899", "subtypes": ["aid", "rescue"]},
    "cultural": {"name": "Cultural & Educational", "icon": "🎓", "color": "#06b6d4", "subtypes": ["exchange", "heritage"]},
    "other": {"name": "Other", "icon": "🔹", "color": "#94a3b8", "subtypes": []}
}

def rebuild():
    manifest = {
        "version": "3.0",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "categories": CATEGORIES,
        "byCategory": {},
        "interactionsById": {}
    }

    for cat_id in CATEGORIES.keys():
        cat_dir = INTERACTIONS_DIR / cat_id
        manifest["byCategory"][cat_id] = []
        
        if not cat_dir.exists():
            continue
            
        print(f"Processing category: {cat_id}")
        for file in cat_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Extract sources
                    sources_list = data.get("sources", [])
                    # Clean up null URLs for manifest
                    sources_list = [s for s in sources_list if isinstance(s, dict) and s.get("url")]

                    # Extract fields needed by InteractionManager (manifest index)
                    entry = {
                        "id": data.get("id", file.stem),
                        "name": data.get("name", file.stem.replace('_', ' ').title()),
                        "category": cat_id,
                        "subtype": (data.get("subtype") or data.get("classification", {}).get("type") or data.get("type") or "general"),
                        "type_label": None,
                        "type": None,
                        "status": data.get("status") or data.get("classification", {}).get("status", "Active"),
                        "participants": data.get("participants") or [c["iso"] for c in data.get("claimants", []) if "iso" in c],
                        "short_description": data.get("short_description") or data.get("description", ""),
                        "description": data.get("description", "") or data.get("short_description") or "",
                        "file": f"{cat_id}/{file.stem}.json",
                        "date": data.get("date"),
                        "visualization_type": data.get("visualization_type"),
                        "arc_style": data.get("arc_style"),
                        "location": data.get("location"),
                        "toast_message": data.get("toast_message", ""),
                        "toast_type": data.get("toast_type", "info"),
                        "llm_analysis_cached": bool(data.get("llm_analysis_cached")),
                        "confidence": data.get("confidence"),
                        "source": data.get("source"),
                        "sources": sources_list,
                    }

                    cat_name = (CATEGORIES.get(cat_id) or {}).get("name") or cat_id.title()
                    st = (entry.get("subtype") or "").strip()
                    entry["subtype"] = st.lower() if isinstance(st, str) else "general"
                    entry["type_label"] = f"{cat_name} · {entry['subtype']}" if entry["subtype"] and entry["subtype"] != "general" else cat_name
                    entry["type"] = entry["type_label"]

                    iid = entry["id"]
                    if iid not in manifest["interactionsById"]:
                        manifest["interactionsById"][iid] = entry
                        manifest["byCategory"][cat_id].append(iid)
            except Exception as e:
                print(f"  Error reading {file.name}: {e}")

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    total_interactions = sum(len(v) for v in manifest["byCategory"].values())
    print(f"✅ Rebuilt manifest with {total_interactions} interactions.")

if __name__ == "__main__":
    rebuild()
