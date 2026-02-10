"""
Dump one full LLM request and response to a text file, including fetched articles.
Run from repo root: python tests/manual_scripts/llm_full_dump_to_file.py
Output: data/llm_full_request_response.txt
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env.local", override=False)
    load_dotenv(REPO_ROOT / ".env", override=False)
except Exception:
    pass

from ingestion_engine.services.gdelt_event_aggregator import aggregate
from ingestion_engine.services.article_fetcher import fetch_articles
from ingestion_engine.services.llm_analysis_engine import (
    ANALYSIS_PROMPT,
    OPENROUTER_URL,
    OPENROUTER_API_KEY,
    MODEL,
    _article_excerpts,
)

import requests

def main():
    data = aggregate()
    events = data.get("events", [])
    ev = next(
        (e for e in events if (e.get("source_urls") or []) and len((e.get("source_urls") or [])) > 0),
        events[0],
    )
    urls = (ev.get("source_urls") or [])[:3]
    articles = fetch_articles(urls, use_cache=True) if urls else {}
    article_content = _article_excerpts(articles, max_chars_per=3000, max_total=8000)

    participants = ev.get("participants") or []
    if not isinstance(participants, list):
        participants = [participants] if participants else []
    participant_count = len(participants)
    participants_str = ", ".join(str(p) for p in participants) if participants else "(none)"
    location = ev.get("location")
    location_str = json.dumps(location) if location else "N/A"

    prompt = ANALYSIS_PROMPT.format(
        event_type=ev.get("type", "unknown"),
        participants=participants_str,
        participant_count=participant_count,
        location=location_str,
        description=(ev.get("description") or "")[:500],
        confidence=ev.get("confidence", 0.5),
        source_urls=", ".join((ev.get("source_urls") or [])[:5]),
        article_content=article_content[:12000],
    )

    request_body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a geopolitical analyst. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    r = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json=request_body,
        timeout=90,
    )

    out_path = REPO_ROOT / "data" / "llm_full_request_response.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("EVENT\n")
        f.write("=" * 80 + "\n")
        f.write(f"id: {ev.get('id')}\n")
        f.write(f"description: {ev.get('description')}\n")
        f.write(f"type: {ev.get('type')}\n")
        f.write(f"participants: {ev.get('participants')}\n")
        f.write(f"source_urls: {ev.get('source_urls')}\n")
        f.write("\n")

        f.write("=" * 80 + "\n")
        f.write("ARTICLES FETCHED (URL -> length of text)\n")
        f.write("=" * 80 + "\n")
        for url, text in articles.items():
            f.write(f"\nURL: {url}\n")
            f.write(f"Length: {len(text or '')} chars\n")
            if text:
                f.write(f"Excerpt (first 500 chars):\n{text[:500]}...\n")
        f.write("\n")

        f.write("=" * 80 + "\n")
        f.write("ARTICLE CONTENT INJECTED INTO PROMPT (full text used)\n")
        f.write("=" * 80 + "\n")
        f.write(article_content)
        f.write("\n\n")

        f.write("=" * 80 + "\n")
        f.write("EVERYTHING WE SEND\n")
        f.write("=" * 80 + "\n")
        f.write(f"URL: {OPENROUTER_URL}\n\n")
        f.write("Headers:\n")
        f.write("  Content-Type: application/json\n")
        key_preview = (OPENROUTER_API_KEY[:20] + "...") if OPENROUTER_API_KEY else "(none)"
        f.write(f"  Authorization: Bearer {key_preview}\n\n")
        f.write("Body (full JSON; user message contains the full prompt with articles):\n")
        f.write(json.dumps(request_body, indent=2, ensure_ascii=False))
        f.write("\n\n")

        f.write("=" * 80 + "\n")
        f.write("EVERYTHING WE RECEIVE\n")
        f.write("=" * 80 + "\n")
        f.write(f"Status: {r.status_code}\n\n")
        f.write("Response headers:\n")
        for k, v in r.headers.items():
            f.write(f"  {k}: {v}\n")
        f.write("\nResponse body (full JSON):\n")
        try:
            f.write(json.dumps(r.json(), indent=2, ensure_ascii=False))
        except Exception:
            f.write(r.text)
        f.write("\n")

    print(f"Written to {out_path}")
    print(f"Event: {ev.get('description')}")
    print(f"Articles fetched: {len(articles)}")
    print(f"Article content length in prompt: {len(article_content)} chars")


if __name__ == "__main__":
    main()
