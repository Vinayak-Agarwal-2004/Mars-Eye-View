"""
Article Fetcher: fetches full-text content from URLs.
Bridge until the full news scraper exists. Used by LLM Analysis Engine.
"""
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "interactions" / "cache" / "articles"
DEFAULT_TIMEOUT = 15
MAX_TEXT_LENGTH = 150000


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _fetch_with_requests(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "GDELT-Streamer/1.0"})
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _extract_text_readability(html: str) -> Optional[str]:
    try:
        from readability import Document
        doc = Document(html)
        return doc.summary()
    except Exception:
        return None


def _extract_text_bs4(html: str) -> Optional[str]:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in ("script", "style", "nav", "footer", "header"):
            for e in soup.find_all(tag):
                e.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:MAX_TEXT_LENGTH] if text else None
    except Exception:
        return None


def _extract_text(html: str) -> Optional[str]:
    text = _extract_text_readability(html)
    if text and len(text.strip()) > 100:
        return text[:MAX_TEXT_LENGTH]
    text = _extract_text_bs4(html)
    return text


def fetch_article(url: str, use_cache: bool = True, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    if not url or not url.startswith("http"):
        return None
    key = _url_hash(url)
    cache_file = CACHE_DIR / f"{key}.txt"
    if use_cache and cache_file.exists():
        try:
            return cache_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    html = _fetch_with_requests(url, timeout=timeout)
    if not html:
        return None
    text = _extract_text(html)
    if text:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            cache_file.write_text(text, encoding="utf-8")
        except Exception:
            pass
    return text


def fetch_articles(urls: List[str], use_cache: bool = True, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, str]:
    seen = set()
    result = {}
    for url in urls:
        url = (url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        text = fetch_article(url, use_cache=use_cache, timeout=timeout)
        if text:
            result[url] = text
    return result
