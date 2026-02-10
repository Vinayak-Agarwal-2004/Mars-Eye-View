#!/usr/bin/env python3
"""
Build ADM lookup table: name/shapeID -> {name, lat, lon, iso, level}
Precomputes centroids from GeoJSON for Wikipedia geosearch integration.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
COUNTRY_SOURCES = DATA_DIR / "country_sources.json"
OUTPUT = DATA_DIR / "adm_lookup.json"


def _extract_coords(geom) -> list:
    if geom["type"] == "Point":
        return [geom["coordinates"]]
    if geom["type"] == "LineString":
        return geom["coordinates"]
    if geom["type"] == "Polygon":
        return geom["coordinates"][0]
    if geom["type"] == "MultiPolygon":
        out = []
        for ring in geom["coordinates"]:
            out.extend(ring[0])
        return out
    return []


def _centroid(coords: list) -> tuple:
    if not coords:
        return (None, None)
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _get_name(props: dict) -> str:
    return (
        props.get("shapeName")
        or props.get("ADMIN")
        or props.get("NAME")
        or props.get("name")
        or props.get("reg_name")
        or props.get("state_name")
        or props.get("province_name")
        or props.get("LABEL")
        or props.get("Label")
        or "Unknown"
    )


def _get_iso(props: dict, parent_iso: str) -> str:
    iso = (
        props.get("shapeGroup")
        or props.get("ADM0_A3")
        or props.get("ISO_A3")
        or props.get("ISO3166-1-Alpha-3")
        or parent_iso
        or ""
    )
    if iso == "-99":
        iso = props.get("ADM0_A3") or props.get("SOV_A3") or parent_iso or ""
    return iso


def build_lookup() -> dict:
    with open(COUNTRY_SOURCES, "r", encoding="utf-8") as f:
        sources = json.load(f)

    entries = {}
    by_iso_name = {}

    for iso, cfg in sources.items():
        for level, key in [(1, "adm1"), (2, "adm2")]:
            path = cfg.get(key)
            if not path:
                continue
            fp = REPO_ROOT / path
            if not fp.exists():
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            features = data.get("features") or []
            for feat in features:
                geom = feat.get("geometry")
                props = feat.get("properties") or {}
                if not geom:
                    continue
                coords = _extract_coords(geom)
                lat, lon = _centroid(coords)
                if lat is None or lon is None:
                    continue
                name = _get_name(props)
                shape_iso = props.get("shapeISO") or ""
                shape_id = props.get("shapeID") or props.get("shapeName") or name
                iso_val = _get_iso(props, iso)
                entry_key = f"{iso}_{shape_id}_{level}"
                if entry_key in entries:
                    continue
                entry = {
                    "name": name,
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "iso": iso_val,
                    "level": level,
                    "shapeISO": shape_iso or None,
                }
                entries[entry_key] = entry
                by_iso_name.setdefault(iso_val, {})[name] = {"lat": entry["lat"], "lon": entry["lon"], "level": level}

    return {"entries": entries, "by_iso_name": by_iso_name}


def main():
    print("Building ADM lookup...")
    lookup = build_lookup()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(lookup, f, indent=2, ensure_ascii=False)
    n = len(lookup.get("entries", {}))
    print(f"Wrote {OUTPUT} with {n} entries")


if __name__ == "__main__":
    main()
