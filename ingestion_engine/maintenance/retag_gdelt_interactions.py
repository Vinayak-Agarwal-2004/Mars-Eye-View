import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
INTERACTIONS_DIR = DATA_DIR / "interactions"
MANIFEST_PATH = INTERACTIONS_DIR / "manifest.json"


def _infer_category(source: str, name: str, description: str) -> str:
    src = (source or "").lower()
    text = f"{name or ''} {description or ''}".lower()

    def has(*terms: str) -> bool:
        return any(t in text for t in terms if t)

    if src == "gdelt_conflict":
        return "disputes"

    if src == "gdelt_diplomatic":
        if has("military"):
            return "military"
        return "meetings"

    if src == "gdelt":
        if has("sanction", "tariff", "embargo", "trade", "export", "import", "investment", "loan", "currency"):
            return "trade"
        if has("summit", "talks", "dialogue", "negotiation", "meeting", "visit", "delegation"):
            return "meetings"

    return "other"


def retag() -> int:
    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_category = manifest.get("byCategory") or {}
    interactions = manifest.get("interactionsById") or {}
    categories = manifest.get("categories") or {}

    changed = False

    for iid, entry in list(interactions.items()):
        cat = (entry.get("category") or "other").lower()
        src = (entry.get("source") or "").lower()
        if cat != "other":
            continue

        if iid.startswith("anomaly_") or iid.startswith("hotspot_"):
            continue

        name = entry.get("name") or ""
        desc = entry.get("description") or entry.get("short_description") or ""
        new_cat = _infer_category(src, name, desc)
        if not new_cat or new_cat == cat:
            continue

        detail_old = INTERACTIONS_DIR / cat / f"{iid}.json"
        detail_new_dir = INTERACTIONS_DIR / new_cat
        detail_new_dir.mkdir(parents=True, exist_ok=True)
        detail_new = detail_new_dir / f"{iid}.json"

        if detail_old.exists():
            try:
                detail = json.loads(detail_old.read_text(encoding="utf-8"))
            except Exception:
                detail = {}
            detail["category"] = new_cat
            detail.setdefault("source", src)
            try:
                detail_new.write_text(json.dumps(detail, indent=2), encoding="utf-8")
                if detail_old != detail_new and detail_old.exists():
                    detail_old.unlink()
            except Exception as e:
                print(f"Failed to move detail for {iid}: {e}")

        if iid in by_category.get(cat, []):
            by_category[cat] = [x for x in by_category[cat] if x != iid]
        by_category.setdefault(new_cat, []).append(iid)

        entry["category"] = new_cat
        cat_name = (categories.get(new_cat) or {}).get("name") or new_cat.title()
        subtype = (entry.get("subtype") or "general").lower()
        type_label = f"{cat_name} · {subtype}" if subtype and subtype != "general" else cat_name
        entry["type_label"] = type_label
        entry["type"] = type_label

        interactions[iid] = entry
        changed = True

    if not changed:
        print("No GDELT interactions needed retagging.")
        return 0

    manifest["byCategory"] = by_category
    manifest["interactionsById"] = interactions
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Retagged GDELT interactions and updated manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(retag())

