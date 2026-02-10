import json
from pathlib import Path
from datetime import datetime


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "interactions" / "manifest.json"


def _type_label(cat_name: str, subtype: str) -> str:
    st = (subtype or "").strip()
    if not st or st.lower() == "general":
        return cat_name
    return f"{cat_name} · {st}"


def migrate():
    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if isinstance(manifest.get("interactionsById"), dict) and isinstance(manifest.get("byCategory"), dict):
        print("Manifest already v3; nothing to do.")
        return 0

    categories = manifest.get("categories") or {}
    interactions = manifest.get("interactions") or {}

    out = {
        "version": "3.0",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "categories": categories,
        "byCategory": {},
        "interactionsById": {},
    }

    seen = set()
    for cat_id, entries in interactions.items():
        if not isinstance(entries, list):
            continue
        out["byCategory"].setdefault(cat_id, [])
        cat_name = (categories.get(cat_id) or {}).get("name") or str(cat_id).title()

        for e in entries:
            if not isinstance(e, dict):
                continue
            iid = e.get("id")
            if not iid or iid in seen:
                continue
            seen.add(iid)

            subtype = (e.get("subtype") or e.get("type") or "general").lower()
            type_label = _type_label(cat_name, subtype)

            entry = {k: v for k, v in e.items() if k not in ("llm_analysis",)}
            entry["id"] = iid
            entry["category"] = (e.get("category") or cat_id or "other").lower()
            entry["subtype"] = subtype
            entry["type_label"] = entry.get("type_label") or type_label
            entry["type"] = entry.get("type") or entry["type_label"]
            entry["short_description"] = entry.get("short_description") or entry.get("description") or ""
            entry["description"] = entry.get("description") or entry["short_description"]
            entry["llm_analysis_cached"] = bool(e.get("llm_analysis_cached"))

            out["interactionsById"][iid] = entry
            out["byCategory"][cat_id].append(iid)

    MANIFEST_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Migrated manifest to v3: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(migrate())

