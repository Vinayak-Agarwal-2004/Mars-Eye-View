"""
LLM Analysis Engine: combines GDELT event data + article content into
refined analysis and interaction metadata (visualization_type, arc_style, toast, etc.).
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "interactions" / "cache" / "llm_analysis"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

ANALYSIS_PROMPT = """You are analyzing a geopolitical event for a map visualization. Output only valid JSON.

GDELT Event Data:
- Type: {event_type}
- Participants (countries/actors): {participants}
- Participant count: {participant_count} (use this to decide visualization_type)
- Location: {location}
- Description: {description}
- Confidence: {confidence}
- Source URLs: {source_urls}

Related Articles (excerpts):
{article_content}

{wiki_context}

RULES (follow strictly):
1. visualization_type:
   - When Participant count is 2 or more, use "geodesic" (arc between two countries). Geodesic draws an arc between the first two countries in Participants.
   - Use "geodesic" ONLY when there are at least TWO distinct countries in Participants (e.g. "USA, China" or "Israel, Lebanon").
   - Use "dot" in ALL other cases: when Participants is empty, when there is only one country/actor, when the event is about a single location/hotspot/anomaly/actor, or when the event type is anomaly/hotspot/location/actor. Dot shows a single point on the map.
2. For "dot" you MUST set location. Use event Location if given (lat/lon), or infer from description (e.g. "Israel" -> {{"iso": "ISR"}}, "United States" -> {{"iso": "USA"}}). Format: {{"lat": number, "lon": number}} or {{"iso": "XXX"}}. For "geodesic" set location to null.
3. arc_style: "dashed" | "solid" | "dotted" (only for geodesic; use "solid" if dot).
4. analysis: A long, structured summary (plain text). (a) Briefly summarise each linked article in turn (one short paragraph per source). (b) Then synthesise how they relate: agreement, contradiction, or different angles. (c) Then state the overall picture and implications in 1-2 short paragraphs. Use double newlines between paragraphs so the text can be rendered with clear breaks. If there are no articles, still provide a 2-4 sentence analysis from the GDELT description alone.
5. toast_message: one short line for a notification.
6. toast_type: "info" | "success" | "warning" | "error".
7. confidence: 0.0-1.0.

Return valid JSON only with keys: analysis, visualization_type, arc_style, location, toast_message, toast_type, confidence."""


def _call_openrouter(prompt: str) -> tuple[Optional[str], Optional[int]]:
    if not OPENROUTER_API_KEY:
        return None, None
    import requests
    try:
        r = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are a geopolitical analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        if r.status_code == 429 or r.status_code >= 500:
            return None, r.status_code
        r.raise_for_status()
        return r.json().get("choices", [{}])[0].get("message", {}).get("content"), None
    except Exception as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        return None, status


def _call_groq(prompt: str) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        import requests
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a geopolitical analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json().get("choices", [{}])[0].get("message", {}).get("content")
    except Exception:
        return None


_llm_provider_stats = {"openrouter_ok": 0, "openrouter_fail": 0, "groq_ok": 0, "groq_fail": 0}


def _call_llm(prompt: str) -> Optional[str]:
    if OPENROUTER_API_KEY:
        out, status = _call_openrouter(prompt)
        if out:
            _llm_provider_stats["openrouter_ok"] += 1
            return out
        if status is not None:
            _llm_provider_stats["openrouter_fail"] += 1
            if status == 429:
                print(f"[LLM] OpenRouter rate limit (429), falling back to Groq")
            else:
                print(f"[LLM] OpenRouter failed ({status}), falling back to Groq")
    if GROQ_API_KEY:
        out = _call_groq(prompt)
        if out:
            _llm_provider_stats["groq_ok"] += 1
            return out
        _llm_provider_stats["groq_fail"] += 1
    return None


def get_llm_provider_stats() -> Dict[str, int]:
    return dict(_llm_provider_stats)


def reset_llm_provider_stats() -> None:
    _llm_provider_stats.update(openrouter_ok=0, openrouter_fail=0, groq_ok=0, groq_fail=0)


def _article_excerpts(articles: Dict[str, str], max_chars_per: int = 3000, max_total: int = 8000) -> str:
    parts = []
    total = 0
    for url, text in articles.items():
        if not text or total >= max_total:
            continue
        excerpt = (text[:max_chars_per] + "...") if len(text) > max_chars_per else text
        parts.append(f"[Source: {url}]\n{excerpt}")
        total += len(excerpt)
    return "\n\n---\n\n".join(parts) if parts else "No article content available."


_wiki_cache: Dict[str, str] = {}
_MAX_WIKI_CONTEXT = 2000


def _fetch_wiki_context(event: Dict) -> str:
    try:
        from .wikipedia_fetcher import WikipediaFetcher
    except Exception:
        return ""
    fetcher = WikipediaFetcher()
    extracts = []
    seen = set()
    location = event.get("location")
    if isinstance(location, dict) and location.get("iso"):
        iso = location.get("iso")
        if iso and iso not in seen:
            seen.add(iso)
            key = f"iso:{iso}"
            if key not in _wiki_cache:
                result = fetcher.get_best_match(iso, None, None)
                _wiki_cache[key] = (result.get("extract") or "")[:1500] if result else ""
            if _wiki_cache[key]:
                extracts.append(f"[Wikipedia - {iso}]: {_wiki_cache[key]}")
    participants = event.get("participants") or []
    if not isinstance(participants, list):
        participants = [participants] if participants else []
    for p in participants[:3]:
        name = str(p).strip() if p else ""
        if not name or len(name) < 2 or name in seen:
            continue
        seen.add(name)
        key = f"name:{name}"
        if key not in _wiki_cache:
            result = fetcher.get_best_match(name, None, None)
            _wiki_cache[key] = (result.get("extract") or "")[:800] if result else ""
        if _wiki_cache[key]:
            extracts.append(f"[Wikipedia - {name}]: {_wiki_cache[key]}")
    desc = (event.get("description") or "")[:200]
    for token in desc.replace(",", " ").split():
        token = token.strip()
        if len(token) > 4 and token[0].isupper() and token not in seen:
            key = f"desc:{token}"
            if key not in _wiki_cache and len(extracts) < 3:
                result = fetcher.get_best_match(token, None, None)
                _wiki_cache[key] = (result.get("extract") or "")[:500] if result else ""
                if _wiki_cache[key]:
                    extracts.append(f"[Wikipedia - {token}]: {_wiki_cache[key]}")
                    seen.add(token)
                    break
    if not extracts:
        return ""
    total = "\n\n".join(extracts)[:_MAX_WIKI_CONTEXT]
    return f"Wikipedia context:\n{total}"


def analyze_event(
    event: Dict,
    articles: Optional[Dict[str, str]] = None,
    use_cache: bool = True,
    lazy: bool = False,
    return_raw: bool = False,
    return_prompt: bool = False,
    use_wikipedia: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Run LLM analysis on a GDELT event with optional article content.
    If lazy=True, return None without calling LLM (for lazy loading).
    If return_prompt=True, skip cache and return {"prompt": str, "raw_output": str, "parsed": dict}.
    """
    if lazy:
        return None
    event_id = event.get("id") or ""
    if use_cache and not return_prompt and event_id:
        cache_file = CACHE_DIR / f"{event_id}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    articles = articles or {}
    article_content = _article_excerpts(articles)
    wiki_context = _fetch_wiki_context(event) if use_wikipedia else ""
    if wiki_context:
        wiki_context = wiki_context.strip()

    participants = event.get("participants") or []
    if not isinstance(participants, list):
        participants = [participants] if participants else []
    participant_count = len(participants)
    participants_str = ", ".join(str(p) for p in participants) if participants else "(none)"
    location = event.get("location")
    location_str = json.dumps(location) if location else "N/A"

    prompt = ANALYSIS_PROMPT.format(
        event_type=event.get("type", "unknown"),
        participants=participants_str,
        participant_count=participant_count,
        location=location_str,
        description=(event.get("description") or "")[:500],
        confidence=event.get("confidence", 0.5),
        source_urls=", ".join((event.get("source_urls") or [])[:5]),
        article_content=article_content[:12000],
        wiki_context=wiki_context or "(none)",
    )

    raw = _call_llm(prompt)
    if not raw:
        return {"prompt": prompt, "raw_output": "", "parsed": None} if return_prompt else None
    try:
        out = json.loads(raw)
        if not isinstance(out.get("location"), (dict, type(None))):
            out["location"] = None
        vt = (out.get("visualization_type") or "geodesic").lower()
        if vt == "geodesic" and participant_count < 2:
            out["visualization_type"] = "dot"
            if not out.get("location") and location:
                out["location"] = location
        if out.get("visualization_type") == "dot" and not out.get("location") and location:
            out["location"] = location
        if event_id and use_cache and not return_prompt:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            to_cache = {k: v for k, v in out.items() if k != "_raw_llm_json"}
            (CACHE_DIR / f"{event_id}.json").write_text(json.dumps(to_cache, indent=2), encoding="utf-8")
        if return_raw and not return_prompt:
            out["_raw_llm_json"] = raw
        if return_prompt:
            return {"prompt": prompt, "raw_output": raw, "parsed": out}
        return out
    except json.JSONDecodeError:
        return {"prompt": prompt, "raw_output": raw, "parsed": None} if return_prompt else None


def analyze_events_with_articles(
    events: List[Dict],
    fetch_articles_fn=None,
    use_cache: bool = True,
    lazy_if_high_confidence: bool = True,
    confidence_threshold: float = 0.7,
    delay_sec: float = 0,
) -> List[Dict]:
    """
    For each event, optionally fetch articles, then run LLM analysis.
    If lazy_if_high_confidence and event confidence >= threshold, skip LLM and return placeholder.
    delay_sec: sleep between events (rate limiting).
    """
    if fetch_articles_fn is None:
        from .article_fetcher import fetch_articles
        fetch_articles_fn = fetch_articles

    results = []
    for i, ev in enumerate(events):
        if delay_sec > 0 and i > 0:
            time.sleep(delay_sec)
        urls = ev.get("source_urls") or []
        articles = fetch_articles_fn(urls, use_cache=use_cache) if urls else {}
        lazy = lazy_if_high_confidence and (ev.get("confidence") or 0) >= confidence_threshold
        analysis = analyze_event(ev, articles=articles, use_cache=use_cache, lazy=lazy)
        if analysis:
            results.append({
                **ev,
                "llm_analysis": analysis.get("analysis", ""),
                "llm_analysis_cached": True,
                "visualization_type": analysis.get("visualization_type", "geodesic"),
                "arc_style": analysis.get("arc_style", "solid"),
                "location": analysis.get("location") or ev.get("location"),
                "toast_message": analysis.get("toast_message", ""),
                "toast_type": analysis.get("toast_type", "info"),
                "confidence": analysis.get("confidence", ev.get("confidence", 0.5)),
            })
        else:
            participants = ev.get("participants") or []
            vt = ev.get("visualization_type") or ("dot" if not participants else "geodesic")
            results.append({
                **ev,
                "llm_analysis": "",
                "llm_analysis_cached": False,
                "visualization_type": vt,
                "arc_style": ev.get("arc_style", "solid"),
                "location": ev.get("location"),
                "toast_message": ev.get("toast_message", ""),
                "toast_type": ev.get("toast_type", "info"),
            })
    return results
