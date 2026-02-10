"""
GDELT Event Aggregator: collects events from hotspots, anomalies, DBSCAN,
diplomatic tracker, and conflict monitor with source URLs and confidence scores.
Output format is canonical for the LLM analysis pipeline.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
LIVE_DIR = DATA_DIR / "live"
HOTSPOT_FILE = LIVE_DIR / "hotspots_latest.json"
HISTORY_FILE = LIVE_DIR / "gdelt_window.json"


def _source_urls_from_top_sources(top_sources: List) -> List[str]:
    urls = []
    for item in top_sources or []:
        if isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
        elif isinstance(item, (list, tuple)) and len(item) >= 1:
            urls.append(item[0])
    return urls


def _confidence_from_sources(source_count: int, event_count: int = 1) -> float:
    if source_count >= 10 and event_count >= 5:
        return 0.9
    if source_count >= 5 or event_count >= 3:
        return 0.75
    if source_count >= 2:
        return 0.6
    return 0.4


def collect_from_hotspots(max_location: int = 5, max_event: int = 5, max_actor: int = 5) -> List[Dict]:
    events = []
    if not HOTSPOT_FILE.exists():
        return events

    with open(HOTSPOT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    hotspots = data.get("hotspots") or {}
    now = datetime.now(timezone.utc).isoformat()

    for kind, key in [("location", "location"), ("event", "event"), ("actor", "actor")]:
        items = hotspots.get(kind) or []
        limit = max_location if kind == "location" else (max_event if kind == "event" else max_actor)
        for i, item in enumerate(items[:limit]):
            key_val = item.get("key", "")
            count = item.get("count", 0)
            top_sources = item.get("top_sources") or []
            source_urls = []
            for x in top_sources:
                if isinstance(x, dict) and x.get("url"):
                    source_urls.append(x["url"])
                elif isinstance(x, (list, tuple)) and len(x) >= 1:
                    source_urls.append(x[0])

            loc_name = key_val
            if kind == "location":
                loc_name = (item.get("locations") or [key_val])[0] if item.get("locations") else key_val
            elif kind == "event":
                parts = (key_val or "").split("|")
                loc_name = parts[-1] if len(parts) >= 3 else key_val
            center_lat = item.get("center_lat")
            center_lng = item.get("center_lng")

            events.append({
                "id": f"gdelt_hotspot_{kind}_{i}_{hash(key_val) % 10**8}",
                "source": "hotspot",
                "type": kind,
                "participants": [],
                "location": {"lat": center_lat, "lon": center_lng} if (center_lat is not None and center_lng is not None) else None,
                "description": f"Hotspot: {kind} {loc_name} ({count} events)",
                "confidence": _confidence_from_sources(len(source_urls), count),
                "source_urls": source_urls[:10],
                "gdelt_metadata": {"count": count, "key": key_val, "categories": item.get("categories", [])},
                "collected_at": now,
            })
    return events


def collect_from_anomalies(history_path: Optional[Path] = None, max_anomalies: int = 10) -> List[Dict]:
    events = []
    history_path = history_path or HISTORY_FILE
    if not history_path.exists():
        return events

    with open(history_path, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    _hd = history_data

    class _FakeFirehose:
        history_data = _hd

    try:
        from server.app.services.hotspot import HotspotAnalyzer
        analyzer = HotspotAnalyzer(_FakeFirehose())
        result = analyzer.detect_anomalies(lookback_days=7, sigma_threshold=2.5, transnational=False)
    except Exception:
        return events

    anomalies = result.get("anomalies") or []
    now = datetime.now(timezone.utc).isoformat()

    for i, a in enumerate(anomalies[:max_anomalies]):
        top_sources = a.get("top_sources") or []
        source_urls = [s.get("url") for s in top_sources if isinstance(s, dict) and s.get("url")]
        z = a.get("z_score", 0)
        confidence = min(0.95, 0.5 + z * 0.1)

        events.append({
            "id": f"gdelt_anomaly_{i}_{hash(a.get('grid_key', '')) % 10**8}",
            "source": "anomaly",
            "type": "anomaly",
            "participants": [],
            "location": None,
            "description": f"Anomaly: {a.get('location', 'Unknown')} - {a.get('percent_above_normal', 0)}% above normal (z={z})",
            "confidence": confidence,
            "source_urls": source_urls[:10],
            "gdelt_metadata": {
                "z_score": z,
                "severity": a.get("severity"),
                "current_count": a.get("current_count"),
                "baseline_mean": a.get("baseline_mean"),
            },
            "collected_at": now,
        })
    return events


def collect_from_diplomatic(db_path: Optional[Path] = None, days: int = 7, limit: int = 20) -> List[Dict]:
    events = []
    db_path = db_path or REPO_ROOT / "data" / "gdelt_diplomacy.duckdb"
    if not db_path.exists():
        return events

    try:
        import duckdb
        db = duckdb.connect(str(db_path))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
        result = db.execute("""
            SELECT Source_Country, Target_Country, interaction_type, NumSources,
                   GoldsteinScale, SourceURL, EventDate
            FROM country_interactions
            WHERE EventDate >= ?
            ORDER BY NumSources DESC
            LIMIT ?
        """, [cutoff, limit]).fetchall()
        db.close()
    except Exception:
        return events

    now = datetime.now(timezone.utc).isoformat()
    for i, row in enumerate(result):
        src, tgt, itype, num_src, goldstein, url, evt_date = row
        participants = [str(src), str(tgt)] if src and tgt else []
        source_urls = [url] if url else []
        confidence = _confidence_from_sources(num_src or 0, 1)

        events.append({
            "id": f"gdelt_diplomatic_{i}_{hash(f'{src}-{tgt}-{evt_date}') % 10**8}",
            "source": "gdelt_diplomatic",
            "type": itype or "diplomatic",
            "participants": participants,
            "location": None,
            "description": f"Diplomatic: {src}-{tgt} ({itype})",
            "confidence": confidence,
            "source_urls": source_urls,
            "gdelt_metadata": {"NumSources": num_src, "GoldsteinScale": goldstein, "EventDate": str(evt_date)},
            "collected_at": now,
        })
    return events


def collect_from_conflict(db_path: Optional[Path] = None, days: int = 7, limit: int = 20) -> List[Dict]:
    events = []
    db_path = db_path or REPO_ROOT / "data" / "gdelt_conflicts.duckdb"
    if not db_path.exists():
        return events

    try:
        import duckdb
        db = duckdb.connect(str(db_path))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
        result = db.execute("""
            SELECT Actor1CountryCode, Actor2CountryCode, ActionGeo_FullName,
                   event_category, NumSources, severity_score, SourceURL
            FROM conflict_events
            WHERE EventDate >= ?
            ORDER BY severity_score DESC, NumSources DESC
            LIMIT ?
        """, [cutoff, limit]).fetchall()
        db.close()
    except Exception:
        return events

    now = datetime.now(timezone.utc).isoformat()
    for i, row in enumerate(result):
        a1, a2, location, category, num_src, severity, url = row
        participants = [str(a1), str(a2)] if a1 and a2 else []
        source_urls = [url] if url else []
        confidence = min(0.9, 0.3 + (num_src or 0) * 0.05 + (severity or 0) * 0.02)

        events.append({
            "id": f"gdelt_conflict_{i}_{hash(f'{a1}-{a2}-{location}') % 10**8}",
            "source": "gdelt_conflict",
            "type": category or "conflict",
            "participants": participants,
            "location": None,
            "description": f"Conflict: {location or 'Unknown'} ({category})",
            "confidence": confidence,
            "source_urls": source_urls,
            "gdelt_metadata": {"NumSources": num_src, "severity_score": severity},
            "collected_at": now,
        })
    return events


def aggregate(
    include_hotspots: bool = True,
    include_anomalies: bool = True,
    include_diplomatic: bool = True,
    include_conflict: bool = True,
    max_per_source: int = 10,
) -> Dict[str, Any]:
    events = []
    if include_hotspots:
        events.extend(collect_from_hotspots(max_location=5, max_event=5, max_actor=5))
    if include_anomalies:
        events.extend(collect_from_anomalies(max_anomalies=max_per_source))
    if include_diplomatic:
        events.extend(collect_from_diplomatic(days=7, limit=max_per_source))
    if include_conflict:
        events.extend(collect_from_conflict(days=7, limit=max_per_source))

    events.sort(key=lambda e: e.get("confidence", 0), reverse=True)
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total": len(events),
        "events": events,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-hotspots", action="store_true")
    p.add_argument("--no-anomalies", action="store_true")
    p.add_argument("--no-diplomatic", action="store_true")
    p.add_argument("--no-conflict", action="store_true")
    p.add_argument("--max", type=int, default=10)
    p.add_argument("--output", type=str, default="")
    args = p.parse_args()
    out = aggregate(
        include_hotspots=not args.no_hotspots,
        include_anomalies=not args.no_anomalies,
        include_diplomatic=not args.no_diplomatic,
        include_conflict=not args.no_conflict,
        max_per_source=args.max,
    )
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    else:
        print(json.dumps(out, indent=2))
