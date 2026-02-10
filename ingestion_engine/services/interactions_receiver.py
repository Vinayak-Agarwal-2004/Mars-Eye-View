"""
Interactions Receiver: single entry point for events from any source.
Normalizes to canonical schema, validates, then calls manifest writer.
"""
from typing import List, Dict, Any, Optional
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CANONICAL_REQUIRED = {"name", "participants"}
VALID_VISUALIZATION_TYPES = {"geodesic", "dot"}
VALID_ARC_STYLES = {"dashed", "solid", "dotted"}
VALID_TOAST_TYPES = {"info", "success", "warning", "error"}
GDELT_TYPE_TO_CATEGORY = {
    "anomaly": "other",
    "hotspot": "other",
    "location": "other",
    "event": "other",
    "actor": "other",
    "diplomatic": "meetings",
    "conflict": "disputes",
    "violence": "disputes",
    "protest": "disputes",
    "coercion": "disputes",
    "economic": "trade",
    "military": "military",
}


def normalize_llm(event: Dict) -> Dict:
    category = (event.get("category") or event.get("type") or "other").lower()
    subtype = (event.get("subtype") or "general").lower()
    out = {
        "name": event.get("name") or "Unnamed",
        "participants": event.get("participants") or [],
        # Canonical fields: category + subtype. Raw/source "type" should not be treated as subtype.
        "type": category,
        "category": category,
        "subtype": subtype,
        "description": event.get("description") or event.get("short_description") or "",
        "status": event.get("status") or "Active",
        "date": event.get("date"),
        "topology": event.get("topology") or "mesh",
        "hub": event.get("hub"),
        "visualization_type": event.get("visualization_type") or "geodesic",
        "arc_style": event.get("arc_style") or "solid",
        "location": event.get("location"),
        "toast_message": event.get("toast_message") or "",
        "toast_type": event.get("toast_type") or "info",
        "source": event.get("source") or "llm",
        "source_url": event.get("source_url"),
        "source_urls": event.get("source_urls") or ([event["source_url"]] if event.get("source_url") else []),
        "confidence": event.get("confidence", 0.8),
        "llm_analysis": event.get("llm_analysis"),
        "llm_analysis_cached": event.get("llm_analysis_cached", False),
    }
    if not isinstance(out["participants"], list):
        out["participants"] = [out["participants"]] if out["participants"] else []
    return out


def normalize_news_scraper(event: Dict) -> Dict:
    name = event.get("name") or event.get("title") or "Unnamed"
    participants = event.get("participants") or event.get("countries") or []
    if not isinstance(participants, list):
        participants = [participants] if participants else []
    return normalize_llm({
        **event,
        "name": name,
        "participants": participants,
        "source": "news_scraper",
    })


def normalize_gdelt(event: Dict) -> Dict:
    participants = event.get("participants") or []
    if not isinstance(participants, list):
        participants = [participants] if participants else []
    gdelt_type = (event.get("type") or "other").lower()
    category = GDELT_TYPE_TO_CATEGORY.get(gdelt_type, "other")
    name = event.get("name") or event.get("description") or f"GDELT {gdelt_type}"
    if not name or name == "Unnamed":
        name = event.get("description") or f"GDELT {gdelt_type}"
    source_urls = event.get("source_urls") or []
    return {
        "name": name[:200],
        "participants": participants,
        "type": gdelt_type,
        "category": category,
        "subtype": "general",
        "description": event.get("description") or "",
        "status": "Active",
        "date": None,
        "topology": "mesh",
        "hub": None,
        "visualization_type": event.get("visualization_type") or ("dot" if event.get("location") and not participants else "geodesic"),
        "arc_style": event.get("arc_style") or "solid",
        "location": event.get("location"),
        "toast_message": event.get("toast_message") or "",
        "toast_type": event.get("toast_type") or "info",
        "source": event.get("source") or "gdelt",
        "source_url": source_urls[0] if source_urls else None,
        "source_urls": source_urls,
        "confidence": event.get("confidence", 0.5),
        "llm_analysis": event.get("llm_analysis"),
        "llm_analysis_cached": event.get("llm_analysis_cached", False),
        "gdelt_metadata": event.get("gdelt_metadata"),
    }


def normalize_event(event: Dict, source: str) -> Dict:
    source = (source or "llm").lower()
    if source == "news_scraper":
        return normalize_news_scraper(event)
    if source in ("gdelt_conflict", "gdelt_diplomatic", "gdelt_anomaly", "gdelt", "hotspot", "anomaly"):
        return normalize_gdelt(event)
    return normalize_llm({**event, "source": source})


def validate_canonical(event: Dict) -> Optional[str]:
    if not event.get("name"):
        return "missing name"
    participants = event.get("participants")
    if not isinstance(participants, list):
        return "participants must be a list"
    vt = event.get("visualization_type") or "geodesic"
    if vt not in VALID_VISUALIZATION_TYPES:
        event["visualization_type"] = "geodesic"
    if event.get("arc_style") and event["arc_style"] not in VALID_ARC_STYLES:
        event["arc_style"] = "solid"
    if event.get("toast_type") and event["toast_type"] not in VALID_TOAST_TYPES:
        event["toast_type"] = "info"
    return None


def receive_events(events: List[Dict], source: str = "llm") -> Dict[str, Any]:
    """
    Normalize, validate, and pass events to manifest writer.
    source: one of llm, news_scraper, gdelt_conflict, gdelt_diplomatic, gdelt_anomaly, gdelt
    """
    from ingestion_engine.legacy_processors.processors.manifest_writer import process_new_events

    canonical = []
    errors = []
    for i, raw in enumerate(events):
        try:
            norm = normalize_event(raw, source)
            err = validate_canonical(norm)
            if err:
                errors.append({"index": i, "error": err, "name": raw.get("name", "?")})
                continue
            if not norm.get("participants") and norm.get("visualization_type") != "dot":
                errors.append({"index": i, "error": "participants required for geodesic", "name": norm.get("name", "?")})
                continue
            canonical.append(norm)
        except Exception as e:
            errors.append({"index": i, "error": str(e), "name": raw.get("name", "?")})

    if not canonical:
        return {"added": 0, "errors": errors}

    process_new_events(canonical)
    return {"added": len(canonical), "errors": errors}
