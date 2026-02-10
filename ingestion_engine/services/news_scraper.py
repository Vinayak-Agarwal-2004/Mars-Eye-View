"""
News scraper: RSS feeds -> article links -> fetch full text (newspaper3k / readability).
Emits events to raw_news_events.json for the interactions pipeline.
"""
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urlunparse

REPO_ROOT = Path(__file__).resolve().parents[2]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "GDELT-Streamer/1.0 (News aggregator)",
]


def _normalize_url(url: str) -> str:
    if not url or not url.strip():
        return ""
    u = url.strip()
    parsed = urlparse(u)
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))
    return normalized


def _strip_html(html: str, max_len: int = 2000) -> str:
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] if text else ""


def _infer_category_subtype(title: str, description: str) -> Tuple[str, str]:
    text = f"{title or ''} {description or ''}".lower()

    def has(*terms: str) -> bool:
        return any(t in text for t in terms if t)

    if has("ceasefire", "peace deal", "peace accord", "treaty", "agreement", "accord", "mou", "memorandum of understanding", "fta", "free trade agreement", "pact"):
        if has("ceasefire"):
            return "agreements", "ceasefire"
        if has("mou", "memorandum of understanding"):
            return "agreements", "mou"
        if has("fta", "free trade agreement"):
            return "agreements", "fta"
        if has("peace"):
            return "agreements", "peace_accord"
        return "agreements", "treaty"

    if has("summit", "talks", "meet", "meeting", "dialogue", "negotiation", "visit", "delegation"):
        if has("summit"):
            return "meetings", "summit"
        if has("bilateral"):
            return "meetings", "bilateral"
        if has("multilateral"):
            return "meetings", "multilateral"
        if has("state visit", "official visit"):
            return "meetings", "state_visit"
        return "meetings", "bilateral"

    if has("humanitarian", "relief", "aid", "evacuation", "refugee", "medical", "food aid", "disaster"):
        if has("evacuation", "evacuate"):
            return "humanitarian", "evacuation"
        if has("refugee"):
            return "humanitarian", "refugee"
        if has("medical"):
            return "humanitarian", "medical"
        if has("food"):
            return "humanitarian", "food_aid"
        return "humanitarian", "disaster_relief"

    if has("military", "troops", "exercise", "drill", "deployment", "missile", "navy", "air force", "defence", "defense"):
        if has("exercise", "drill"):
            return "military", "exercise"
        if has("deployment", "troops"):
            return "military", "deployment"
        if has("arms deal", "weapons deal"):
            return "military", "arms_deal"
        if has("patrol"):
            return "military", "patrol"
        return "military", "incident"

    if has("sanction", "tariff", "embargo", "trade", "export", "import", "investment", "currency", "loan"):
        if has("sanction"):
            return "trade", "sanction"
        if has("tariff"):
            return "trade", "tariff"
        if has("embargo"):
            return "trade", "embargo"
        if has("investment"):
            return "trade", "investment"
        if has("loan"):
            return "trade", "loan"
        if has("currency"):
            return "trade", "currency"
        return "trade", "investment"

    if has("olympics", "world cup", "tournament", "match", "championship", "cricket", "formula 1"):
        if has("olympics"):
            return "sports", "olympics"
        if has("world cup"):
            return "sports", "world_cup"
        return "sports", "championship"

    if has("cultural", "festival", "education", "exchange", "tourism", "heritage"):
        if has("exchange"):
            return "cultural", "exchange"
        if has("festival"):
            return "cultural", "festival"
        if has("education"):
            return "cultural", "education"
        if has("tourism"):
            return "cultural", "tourism"
        return "cultural", "heritage"

    if has("border", "dispute", "territorial", "sovereignty", "maritime", "incursion", "clash", "tensions"):
        if has("border"):
            return "disputes", "border_crisis"
        if has("maritime"):
            return "disputes", "maritime"
        return "disputes", "territorial"

    return "other", "general"


def _get_feed_urls() -> List[str]:
    try:
        from ingestion_engine.config.manifest_config import RSS_FEED_URLS
        return list(RSS_FEED_URLS)
    except ImportError:
        return [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://feeds.reuters.com/reuters/topNews",
        ]


def _get_raw_news_path() -> Path:
    try:
        from ingestion_engine.config.manifest_config import RAW_NEWS_EVENTS
        return Path(RAW_NEWS_EVENTS)
    except ImportError:
        return REPO_ROOT / "data" / "interactions" / "raw_news_events.json"


def _get_config() -> Dict[str, Any]:
    try:
        from ingestion_engine.config.manifest_config import (
            NEWS_SCRAPER_TIMEOUT,
            NEWS_SCRAPER_DELAY_SEC,
            NEWS_SCRAPER_MAX_RETRIES,
            NEWS_SCRAPER_USE_NEWSPAPER3K,
        )
        return {
            "timeout": NEWS_SCRAPER_TIMEOUT,
            "delay_sec": NEWS_SCRAPER_DELAY_SEC,
            "max_retries": NEWS_SCRAPER_MAX_RETRIES,
            "use_newspaper3k": NEWS_SCRAPER_USE_NEWSPAPER3K,
        }
    except ImportError:
        return {"timeout": 20, "delay_sec": 1.0, "max_retries": 2, "use_newspaper3k": True}


def _fetch_with_newspaper3k(url: str, timeout: int) -> Optional[Dict[str, Any]]:
    try:
        from newspaper import Article
        art = Article(url)
        art.download()
        art.parse()
        pub = art.publish_date
        if pub and hasattr(pub, "isoformat"):
            published = pub.isoformat()
        elif pub:
            published = str(pub)[:10]
        else:
            published = None
        return {
            "title": (art.title or "").strip() or None,
            "text": (art.text or "").strip() or None,
            "authors": list(art.authors) if art.authors else [],
            "published": published,
        }
    except Exception:
        return None


CACHE_DIR = REPO_ROOT / "data" / "interactions" / "cache" / "articles"


def _fetch_and_cache_article(
    url: str,
    use_newspaper3k: bool,
    timeout: int,
    max_retries: int,
    delay_sec: float,
) -> Tuple[Optional[str], Optional[str], Optional[str], List[str]]:
    """Returns (title, description_snippet, published, authors)."""
    from ingestion_engine.services.article_fetcher import fetch_article
    import hashlib
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    cache_file = CACHE_DIR / f"{cache_key}.txt"

    title_override = None
    published = None
    authors: List[str] = []

    if use_newspaper3k:
        for attempt in range(max_retries + 1):
            out = _fetch_with_newspaper3k(url, timeout)
            if out:
                title_override = out.get("title")
                text = out.get("text")
                if text:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    try:
                        cache_file.write_text(text, encoding="utf-8")
                    except Exception:
                        pass
                published = out.get("published")
                authors = out.get("authors") or []
                snippet = (text or "")[:500].replace("\n", " ") if text else ""
                return (title_override, snippet, published, authors)
            if attempt < max_retries:
                time.sleep(delay_sec * (2 ** attempt))

    for attempt in range(max_retries + 1):
        text = fetch_article(url, use_cache=True, timeout=timeout)
        if text:
            snippet = text[:500].replace("\n", " ")
            return (title_override, snippet, published, authors)
        if attempt < max_retries:
            time.sleep(delay_sec * (2 ** attempt))

    return (title_override, None, published, authors)


def _entry_link(entry: Any) -> Optional[str]:
    link = getattr(entry, "link", None) or entry.get("link") if isinstance(entry, dict) else None
    if link:
        return _normalize_url(link)
    links = getattr(entry, "links", None) or (entry.get("links") if isinstance(entry, dict) else None)
    if links:
        for l in links:
            href = getattr(l, "href", None) or (l.get("href") if isinstance(l, dict) else None)
            if href and "http" in str(href):
                return _normalize_url(href)
    return None


def _entry_published(entry: Any) -> Optional[str]:
    published = getattr(entry, "published_parsed", None) or entry.get("published_parsed")
    if published and hasattr(published, "tm_year"):
        try:
            return f"{published.tm_year}-{published.tm_mon:02d}-{published.tm_mday:02d}"
        except Exception:
            pass
    pub = getattr(entry, "published", None) or entry.get("published")
    if pub:
        return str(pub)[:10] if len(str(pub)) >= 10 else str(pub)
    return None


def run(
    feed_urls: List[str] = None,
    max_articles_per_feed: int = 15,
    fetch_full_text: bool = True,
    write_events: bool = True,
    verbose: bool = False,
) -> Dict[str, Any]:
    try:
        import feedparser
    except ImportError:
        return {"error": "feedparser not installed", "events": [], "count": 0, "errors": []}

    config = _get_config()
    timeout = config.get("timeout", 20)
    delay_sec = config.get("delay_sec", 1.0)
    max_retries = config.get("max_retries", 2)
    use_newspaper3k = config.get("use_newspaper3k", True)

    feed_urls = feed_urls or _get_feed_urls()
    events = []
    seen_urls: set = set()
    errors: List[Dict[str, str]] = []

    for rss_url in feed_urls:
        if not rss_url or not rss_url.startswith("http"):
            continue
        try:
            feed = feedparser.parse(rss_url, request_headers={"User-Agent": USER_AGENTS[0]})
        except Exception as e:
            errors.append({"feed": rss_url, "error": str(e)})
            if verbose:
                print(f"Feed error {rss_url}: {e}")
            continue

        count = 0
        for entry in feed.entries:
            if count >= max_articles_per_feed:
                break
            url = _entry_link(entry)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            rss_title = (getattr(entry, "title", None) or entry.get("title") or "").strip() or "Untitled"
            rss_summary = getattr(entry, "summary", None) or entry.get("summary") or entry.get("description") or ""
            summary_plain = _strip_html(str(rss_summary), 400)
            rss_published = _entry_published(entry)

            title = rss_title
            description = summary_plain
            published = rss_published
            authors: List[str] = []

            if fetch_full_text:
                time.sleep(delay_sec)
                try:
                    title_override, snippet, pub, auth = _fetch_and_cache_article(
                        url, use_newspaper3k, timeout, max_retries, delay_sec
                    )
                    if title_override:
                        title = title_override
                    if snippet:
                        description = snippet if len(snippet) > len(description) else description
                    if pub:
                        published = pub
                    if auth:
                        authors = auth
                except Exception as e:
                    errors.append({"url": url, "error": str(e)})
                    if verbose:
                        print(f"Fetch error {url}: {e}")

            cat, sub = _infer_category_subtype(title, description)
            events.append({
                "name": title,
                "title": title,
                "source_url": url,
                "description": description[:400] if description else "",
                "participants": [],
                "countries": [],
                "type": cat,
                "category": cat,
                "subtype": sub,
                "visualization_type": "dot",
                "date": published,
                "authors": authors,
                "source": "news_scraper",
            })
            count += 1

    if write_events and events:
        out_path = _get_raw_news_path()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"events": events, "source": "news_scraper"}, f, indent=2)

    return {
        "events": events,
        "count": len(events),
        "errors": errors,
        "feeds_processed": len([u for u in feed_urls if u and u.startswith("http")]),
    }


def run_from_gdelt_links(
    max_urls: int = 20,
    fetch_full_text: bool = True,
    write_events: bool = True,
    from_latest: bool = True,
    from_hotspots: bool = True,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Extract URLs from GDELT (latest + hotspots), fetch articles, emit events to raw_news_events."""
    from ingestion_engine.services.gdelt_link_extractor import extract_all
    from ingestion_engine.services.article_fetcher import fetch_article

    result = extract_all(
        from_latest=from_latest,
        from_window=False,
        from_hotspots=from_hotspots,
        from_diplomatic=False,
        from_conflict=False,
        max_latest=0,
        max_hotspots_per_section=30,
        dedupe=True,
    )
    pairs = result.get("urls") or []
    urls = [u for u, _ in pairs[:max_urls]]
    if not urls:
        return {"events": [], "count": 0, "errors": [], "gdelt_unique": result.get("unique_count", 0)}

    config = _get_config()
    delay_sec = config.get("delay_sec", 1.0)
    events = []
    errors = []
    for i, url in enumerate(urls):
        if verbose:
            print(f"  [{i+1}/{len(urls)}] {url[:60]}...")
        title = url.split("/")[-1].replace("-", " ").replace("_", " ")[:80] or "GDELT article"
        description = ""
        if fetch_full_text:
            time.sleep(delay_sec)
            try:
                text = fetch_article(url, use_cache=True)
                if text:
                    description = _strip_html(text[:2000], 400)
                    if not description:
                        description = text[:400].replace("\n", " ")
            except Exception as e:
                errors.append({"url": url, "error": str(e)})
        cat, sub = _infer_category_subtype(title, description)
        events.append({
            "name": title,
            "title": title,
            "source_url": url,
            "description": description[:400] if description else "",
            "participants": [],
            "countries": [],
            "type": cat,
            "category": cat,
            "subtype": sub,
            "visualization_type": "dot",
            "source": "news_scraper",
        })

    if write_events and events:
        out_path = _get_raw_news_path()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"events": events, "source": "news_scraper"}, f, indent=2)

    return {
        "events": events,
        "count": len(events),
        "errors": errors,
        "gdelt_unique": result.get("unique_count", 0),
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-fetch", action="store_true", help="Skip fetching full text")
    p.add_argument("--no-write", action="store_true", help="Do not write raw_news_events.json")
    p.add_argument("--max", type=int, default=15, help="Max articles per feed")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--no-newspaper3k", action="store_true", help="Use only readability/requests")
    p.add_argument("--gdelt", type=int, default=0, metavar="N", help="Use GDELT sources: extract N URLs and fetch as events")
    args = p.parse_args()
    import os
    if args.no_newspaper3k:
        os.environ["NEWS_SCRAPER_USE_NEWSPAPER3K"] = "false"

    if args.gdelt > 0:
        result = run_from_gdelt_links(
            max_urls=args.gdelt,
            fetch_full_text=not args.no_fetch,
            write_events=not args.no_write,
            verbose=args.verbose,
        )
        print(f"Collected {result.get('count', 0)} events from GDELT ({result.get('gdelt_unique', 0)} unique URLs)")
    else:
        result = run(
            fetch_full_text=not args.no_fetch,
            write_events=not args.no_write,
            max_articles_per_feed=args.max,
            verbose=args.verbose,
        )
        print(f"Collected {result.get('count', 0)} events from {result.get('feeds_processed', 0)} feeds")
    if result.get("error"):
        print("Error:", result["error"])
    if result.get("errors"):
        print(f"Errors: {len(result['errors'])}")
        for e in result["errors"][:5]:
            print(" ", e)