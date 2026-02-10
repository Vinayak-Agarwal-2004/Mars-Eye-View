from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel

# Local-only secrets loading (gitignored). In production, use a real secrets manager.
try:
    from dotenv import load_dotenv
    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)
except Exception:
    pass


class IngestBody(BaseModel):
    events: List[dict] = []
    source: str = "llm"

from server.app.services.firehose import FirehoseService
from server.app.services.acled import AcledService

app = FastAPI(title="GDELT-Streamer Backend")

# Security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For localhost dev
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
firehose = FirehoseService()
acled = AcledService()

@app.on_event("startup")
def startup_event():
    firehose.start()

@app.get("/")
def root():
    return {"message": "GDELT-Streamer API is running", "endpoints": ["/api/live", "/api/cast"]}

@app.get("/api/health")
def health():

    return {"status": "ok", "firehose_running": firehose.running}

@app.get("/api/live")
def get_live_events():
    """Returns the latest in-memory GDELT state."""
    return firehose.latest_data

@app.get("/api/cast")
def get_cast_forecast(country: str, admin1: str = None, year: int = None):
    """
    Live Proxy: Gets CAST forecast for a specific country/region.
    Fetches from ACLED API if not in cache.
    """
    return acled.get_forecast(country, admin1, year)


# --- Interactions (manifest, LLM analysis, lazy loading) ---
import json
from pathlib import Path

MANIFEST_PATH = Path("data/interactions/manifest.json")
INTERACTIONS_DIR = Path("data/interactions")


def _find_interaction_by_id(interaction_id: str):
    if not MANIFEST_PATH.exists():
        return None, None
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if isinstance(manifest.get("interactionsById"), dict):
        entry = manifest["interactionsById"].get(interaction_id)
        if isinstance(entry, dict):
            return entry, entry.get("category")
    for cat, entries in (manifest.get("interactions") or {}).items():
        for e in entries:
            if e.get("id") == interaction_id:
                return e, cat
    return None, None


@app.get("/api/interactions/{interaction_id}/analysis")
def get_interaction_analysis(interaction_id: str):
    """
    Lazy loading: return LLM analysis for an interaction.
    If cached, return from detail file; else fetch articles, run LLM, cache and return.
    """
    entry, category = _find_interaction_by_id(interaction_id)
    if not entry or not category:
        return {"error": "Interaction not found", "id": interaction_id}
    detail_file = INTERACTIONS_DIR / category / f"{interaction_id}.json"
    if detail_file.exists():
        try:
            detail = json.loads(detail_file.read_text(encoding="utf-8"))
            if detail.get("llm_analysis_cached") and detail.get("llm_analysis"):
                return {"id": interaction_id, "analysis": detail["llm_analysis"], "cached": True}
        except Exception:
            pass

    try:
        from ingestion_engine.services.article_fetcher import fetch_articles
        from ingestion_engine.services.llm_analysis_engine import analyze_event
    except Exception as e:
        return {"error": f"Import failed: {e}", "id": interaction_id}

    source_urls = (entry.get("source_urls") or []) if isinstance(entry.get("source_urls"), list) else []
    if not source_urls and entry.get("sources"):
        source_urls = [s.get("url") for s in entry["sources"] if isinstance(s, dict) and s.get("url")]
    articles = fetch_articles(source_urls, use_cache=True) if source_urls else {}
    event = {
        "id": interaction_id,
        "type": entry.get("type"),
        "participants": entry.get("participants", []),
        "description": entry.get("short_description") or entry.get("description"),
        "confidence": entry.get("confidence"),
        "source_urls": source_urls,
        "location": entry.get("location"),
    }
    result = analyze_event(event, articles=articles, use_cache=True, lazy=False)
    if not result:
        return {"id": interaction_id, "analysis": "", "cached": False}

    analysis_text = result.get("analysis", "")
    if detail_file.exists():
        try:
            detail = json.loads(detail_file.read_text(encoding="utf-8"))
            detail["llm_analysis"] = analysis_text
            detail["llm_analysis_cached"] = True
            detail_file.write_text(json.dumps(detail, indent=2), encoding="utf-8")
        except Exception:
            pass
    manifest_path = MANIFEST_PATH
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest.get("interactionsById"), dict):
                e = manifest["interactionsById"].get(interaction_id)
                if isinstance(e, dict):
                    e["llm_analysis_cached"] = True
                    e.pop("llm_analysis", None)
            else:
                for e in (manifest.get("interactions") or {}).get(category) or []:
                    if e.get("id") == interaction_id:
                        e["llm_analysis_cached"] = True
                        e.pop("llm_analysis", None)
                        break
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except Exception:
            pass

    return {"id": interaction_id, "analysis": analysis_text, "cached": False}


@app.post("/api/interactions/process-gdelt")
def process_gdelt_events():
    """Process GDELT events from aggregator and optionally run LLM analysis."""
    try:
        from ingestion_engine.services.manifest_auto_updater import run_update_gdelt
    except Exception as e:
        return {"error": str(e)}
    return run_update_gdelt()


@app.post("/api/interactions/ingest")
def ingest_interactions(body: IngestBody):
    """Manual ingest: body = { events: [...], source: 'news_scraper' | 'llm' }."""
    try:
        from ingestion_engine.services.interactions_receiver import receive_events
    except Exception as e:
        return {"error": str(e)}
    events = body.events
    source = body.source
    result = receive_events(events, source=source)
    return result


@app.post("/api/interactions/run-news-scraper")
def run_news_scraper():
    """Run RSS news scraper, write raw_news_events.json, then ingest via receiver."""
    try:
        from ingestion_engine.services.news_scraper import run as run_scraper
        from ingestion_engine.services.manifest_auto_updater import run_update_from_files
    except Exception as e:
        return {"error": str(e)}
    scrape_result = run_scraper(fetch_full_text=True, write_events=True)
    if scrape_result.get("error"):
        return scrape_result
    file_result = run_update_from_files()
    return {"scrape": scrape_result, "ingest": file_result.get("news")}


@app.get("/api/interactions/status")
def interactions_status():
    """Status of manifest and processing."""
    if not MANIFEST_PATH.exists():
        return {"manifest_exists": False, "last_updated": None, "total_entries": 0}
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        total = sum(len(v) for v in (manifest.get("interactions") or {}).values())
        return {
            "manifest_exists": True,
            "last_updated": manifest.get("last_updated"),
            "total_entries": total,
        }
    except Exception:
        return {"manifest_exists": False, "last_updated": None, "total_entries": 0}


# --- Wikipedia API (ingestion_engine/wiki.md) ---
from fastapi import Query

ADM_LOOKUP_PATH = Path("data/adm_lookup.json")
_wiki_fetcher = None
_adm_lookup = None


def _get_wiki_fetcher():
    global _wiki_fetcher
    if _wiki_fetcher is None:
        from ingestion_engine.services.wikipedia_fetcher import WikipediaFetcher
        _wiki_fetcher = WikipediaFetcher()
    return _wiki_fetcher


def _get_adm_lookup():
    global _adm_lookup
    if _adm_lookup is None and ADM_LOOKUP_PATH.exists():
        try:
            _adm_lookup = json.loads(ADM_LOOKUP_PATH.read_text(encoding="utf-8"))
        except Exception:
            _adm_lookup = {"entries": {}, "by_iso_name": {}}
    if _adm_lookup is None:
        _adm_lookup = {"entries": {}, "by_iso_name": {}}
    return _adm_lookup


@app.get("/api/wikipedia/page")
def get_wikipedia_page(title: str = Query(..., min_length=1)):
    """Returns { title, url, extract, thumbnail, pageid } for a Wikipedia page."""
    wf = _get_wiki_fetcher()
    result = wf.get_by_title(title)
    if not result:
        return {"error": "Page not found", "title": title}
    return {"title": result["title"], "url": result["fullurl"], "extract": result["extract"],
            "thumbnail": result["thumbnail"], "pageid": result["pageid"]}


@app.get("/api/wikipedia/geosearch")
def get_wikipedia_geosearch(lat: float = Query(...), lon: float = Query(...),
                           radius: int = Query(10000, ge=100, le=50000),
                           limit: int = Query(5, ge=1, le=20)):
    """Returns geosearch results near coordinates."""
    wf = _get_wiki_fetcher()
    results = wf.get_by_geosearch(lat, lon, radius=radius, limit=limit)
    return {"results": results}


@app.get("/api/wikipedia/lookup")
def get_wikipedia_lookup(place: str = Query(..., min_length=1), lat: float = Query(None),
                        lon: float = Query(None), iso: str = Query(None)):
    """Best-match: title first, fallback to geosearch. Uses ADM lookup for coords if lat/lon missing."""
    wf = _get_wiki_fetcher()
    lookup = _get_adm_lookup()
    lat_val, lon_val = lat, lon
    if lat_val is None or lon_val is None:
        by_iso = lookup.get("by_iso_name", {})
        for check_iso in ([iso] if iso else list(by_iso.keys())):
            places = by_iso.get(check_iso, {})
            if place in places:
                lat_val = places[place]["lat"]
                lon_val = places[place]["lon"]
                break
        if lat_val is None and by_iso:
            for check_iso, places in by_iso.items():
                if place in places:
                    lat_val = places[place]["lat"]
                    lon_val = places[place]["lon"]
                    break
    result = wf.get_best_match(place.strip(), lat_val, lon_val)
    if not result:
        return {"error": "No Wikipedia page found", "place": place}
    return {"title": result["title"], "url": result["fullurl"], "extract": result["extract"],
            "thumbnail": result["thumbnail"], "pageid": result["pageid"]}


@app.get("/api/wikipedia/html")
def get_wikipedia_html(title: str = Query(..., min_length=1)):
    """Mobile-sections HTML for side panel embedding."""
    wf = _get_wiki_fetcher()
    data = wf.get_mobile_sections(title)
    if not data:
        return {"error": "Page not found", "title": title}
    return data
