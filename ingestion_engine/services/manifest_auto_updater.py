"""
Manifest Auto-Updater: watches for new events (raw_llm_events.json, raw_news_events.json)
and processes them through the Interactions Receiver.
Can be triggered manually or by file mtime check.
"""
import json
from pathlib import Path
from typing import Dict, Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_events(path: Path) -> list:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception:
        return []


def run_update_from_files(
    raw_llm_path: Path = None,
    raw_news_path: Path = None,
) -> Dict[str, Any]:
    from ingestion_engine.services.interactions_receiver import receive_events
    try:
        from ingestion_engine.config.manifest_config import RAW_LLM_EVENTS, RAW_NEWS_EVENTS
    except ImportError:
        RAW_LLM_EVENTS = REPO_ROOT / "data" / "interactions" / "raw_llm_events.json"
        RAW_NEWS_EVENTS = REPO_ROOT / "data" / "interactions" / "raw_news_events.json"

    raw_llm_path = raw_llm_path or RAW_LLM_EVENTS
    raw_news_path = raw_news_path or RAW_NEWS_EVENTS

    results = {"llm": None, "news": None}
    events_llm = _load_events(raw_llm_path)
    if events_llm:
        results["llm"] = receive_events(events_llm, source="llm")

    events_news = _load_events(raw_news_path)
    if events_news:
        results["news"] = receive_events(events_news, source="news_scraper")

    return results


def run_update_gdelt() -> Dict[str, Any]:
    """Run GDELT aggregator, send all events through LLM, then submit via receiver."""
    try:
        from ingestion_engine.services.gdelt_event_aggregator import aggregate
        from ingestion_engine.services.llm_analysis_engine import analyze_events_with_articles
        from ingestion_engine.services.interactions_receiver import receive_events
        from ingestion_engine.config.manifest_config import (
            GDELT_LLM_MAX_PER_RUN,
            GDELT_LLM_DELAY_SEC,
        )
    except Exception as e:
        return {"error": str(e)}

    from ingestion_engine.services.llm_analysis_engine import reset_llm_provider_stats, get_llm_provider_stats
    reset_llm_provider_stats()
    data = aggregate()
    events = data.get("events", [])
    if GDELT_LLM_MAX_PER_RUN > 0:
        events = events[:GDELT_LLM_MAX_PER_RUN]
    enriched = analyze_events_with_articles(
        events,
        use_cache=True,
        lazy_if_high_confidence=False,
        delay_sec=GDELT_LLM_DELAY_SEC,
    )
    to_submit = enriched
    result = receive_events(to_submit, source="gdelt")
    llm_stats = get_llm_provider_stats()
    return {
        "aggregated": len(data.get("events", [])),
        "submitted": len(to_submit),
        "llm_provider": llm_stats,
        **result,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--from-files", action="store_true", help="Process raw_llm_events.json and raw_news_events.json")
    p.add_argument("--gdelt", action="store_true", help="Run GDELT aggregator and process")
    args = p.parse_args()
    if args.gdelt:
        print(run_update_gdelt())
    elif args.from_files:
        print(run_update_from_files())
    else:
        print("Use --from-files or --gdelt")
