"""
Extract article/source URLs from GDELT data: gdelt_latest, gdelt_window,
hotspots_latest, and optional DuckDB (diplomatic, conflict).
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
LIVE_DIR = DATA_DIR / "live"


def _normalize_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if not u.startswith("http"):
        return ""
    parsed = urlparse(u)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}{'?' + parsed.query if parsed.query else ''}"


def _urls_from_feature(feat: Dict) -> List[str]:
    out = []
    props = feat.get("properties") or {}
    primary = props.get("sourceurl")
    if primary:
        out.append(primary)
    for s in props.get("sources") or []:
        u = s.get("url") if isinstance(s, dict) else None
        if u:
            out.append(u)
    return out


def extract_from_gdelt_latest(path: Path = None, max_features: int = 0) -> List[Tuple[str, str]]:
    """(url, context) with context e.g. 'gdelt_latest'."""
    path = path or LIVE_DIR / "gdelt_latest.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    features = data.get("features") or []
    if max_features > 0:
        features = features[:max_features]
    out = []
    for f in features:
        for u in _urls_from_feature(f):
            norm = _normalize_url(u)
            if norm:
                out.append((norm, "gdelt_latest"))
    return out


def extract_from_gdelt_window(path: Path = None, max_features: int = 0) -> List[Tuple[str, str]]:
    path = path or LIVE_DIR / "gdelt_window.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    features = data.get("features") or []
    if max_features > 0:
        features = features[:max_features]
    out = []
    for f in features:
        for u in _urls_from_feature(f):
            norm = _normalize_url(u)
            if norm:
                out.append((norm, "gdelt_window"))
    return out


def extract_from_hotspots(path: Path = None, max_urls_per_section: int = 50) -> List[Tuple[str, str]]:
    """top_sources are [url, count] or [{"url": u}, ...]."""
    path = path or LIVE_DIR / "hotspots_latest.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    hotspots = data.get("hotspots") or {}
    out = []
    for kind in ("location", "event", "actor"):
        items = hotspots.get(kind) or []
        count = 0
        for item in items:
            if max_urls_per_section > 0 and count >= max_urls_per_section:
                break
            top_sources = item.get("top_sources") or []
            for x in top_sources:
                if max_urls_per_section > 0 and count >= max_urls_per_section:
                    break
                if isinstance(x, (list, tuple)) and len(x) >= 1:
                    u = x[0]
                elif isinstance(x, dict) and x.get("url"):
                    u = x["url"]
                else:
                    continue
                norm = _normalize_url(u)
                if norm:
                    out.append((norm, f"hotspots_{kind}"))
                    count += 1
    return out


def extract_from_diplomatic(db_path: Path = None, limit: int = 100) -> List[Tuple[str, str]]:
    db_path = db_path or REPO_ROOT / "data" / "gdelt_diplomacy.duckdb"
    if not db_path.exists():
        return []
    try:
        import duckdb
        db = duckdb.connect(str(db_path))
        rows = db.execute(
            "SELECT DISTINCT SourceURL FROM country_interactions WHERE SourceURL IS NOT NULL AND SourceURL != '' LIMIT ?",
            [limit],
        ).fetchall()
        db.close()
        return [(_normalize_url(r[0]), "gdelt_diplomatic") for r in rows if _normalize_url(r[0])]
    except Exception:
        return []


def extract_from_conflict(db_path: Path = None, limit: int = 100) -> List[Tuple[str, str]]:
    db_path = db_path or REPO_ROOT / "data" / "gdelt_conflicts.duckdb"
    if not db_path.exists():
        return []
    try:
        import duckdb
        db = duckdb.connect(str(db_path))
        rows = db.execute(
            "SELECT DISTINCT SourceURL FROM conflict_events WHERE SourceURL IS NOT NULL AND SourceURL != '' LIMIT ?",
            [limit],
        ).fetchall()
        db.close()
        return [(_normalize_url(r[0]), "gdelt_conflict") for r in rows if _normalize_url(r[0])]
    except Exception:
        return []


def extract_all(
    from_latest: bool = True,
    from_window: bool = True,
    from_hotspots: bool = True,
    from_diplomatic: bool = True,
    from_conflict: bool = True,
    max_latest: int = 0,
    max_window: int = 0,
    max_hotspots_per_section: int = 50,
    diplomatic_limit: int = 100,
    conflict_limit: int = 100,
    dedupe: bool = True,
) -> Dict[str, Any]:
    """Collect URLs from all enabled GDELT sources. Returns {urls: [(url, context)], unique_count, by_source: {context: count}}."""
    all_pairs: List[Tuple[str, str]] = []
    if from_latest:
        all_pairs.extend(extract_from_gdelt_latest(max_features=max_latest))
    if from_window:
        all_pairs.extend(extract_from_gdelt_window(max_features=max_window))
    if from_hotspots:
        all_pairs.extend(extract_from_hotspots(max_urls_per_section=max_hotspots_per_section))
    if from_diplomatic:
        all_pairs.extend(extract_from_diplomatic(limit=diplomatic_limit))
    if from_conflict:
        all_pairs.extend(extract_from_conflict(limit=conflict_limit))

    by_source: Dict[str, int] = {}
    for _, ctx in all_pairs:
        by_source[ctx] = by_source.get(ctx, 0) + 1

    if dedupe:
        seen: Set[str] = set()
        unique = []
        for u, ctx in all_pairs:
            if u not in seen:
                seen.add(u)
                unique.append((u, ctx))
        all_pairs = unique

    return {
        "urls": all_pairs,
        "unique_count": len(all_pairs),
        "by_source": by_source,
    }


def fetch_sample(urls: List[str], max_fetch: int = 5) -> Dict[str, Any]:
    """Fetch up to max_fetch URLs via article_fetcher; return {fetched: count, results: [(url, len(text))]}."""
    from ingestion_engine.services.article_fetcher import fetch_article

    results = []
    for u in urls[:max_fetch]:
        text = fetch_article(u, use_cache=True)
        results.append((u, len(text) if text else 0))
    return {"fetched": len(results), "results": results}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Extract source URLs from GDELT data")
    p.add_argument("--no-latest", action="store_true", help="Skip gdelt_latest.json")
    p.add_argument("--no-window", action="store_true", help="Skip gdelt_window.json")
    p.add_argument("--no-hotspots", action="store_true", help="Skip hotspots_latest.json")
    p.add_argument("--no-diplomatic", action="store_true", help="Skip diplomatic DuckDB")
    p.add_argument("--no-conflict", action="store_true", help="Skip conflict DuckDB")
    p.add_argument("--max-latest", type=int, default=0, help="Max features from latest (0=all)")
    p.add_argument("--max-window", type=int, default=0, help="Max features from window (0=all)")
    p.add_argument("--max-hotspots", type=int, default=50, help="Max URLs per hotspot section")
    p.add_argument("--fetch", type=int, default=0, metavar="N", help="Fetch first N URLs with article_fetcher")
    p.add_argument("--print", action="store_true", dest="print_urls", help="Print each URL")
    args = p.parse_args()

    result = extract_all(
        from_latest=not args.no_latest,
        from_window=not args.no_window,
        from_hotspots=not args.no_hotspots,
        from_diplomatic=not args.no_diplomatic,
        from_conflict=not args.no_conflict,
        max_latest=args.max_latest,
        max_window=args.max_window,
        max_hotspots_per_section=args.max_hotspots,
        dedupe=True,
    )

    print(f"Unique URLs: {result['unique_count']}")
    print("By source:", result["by_source"])

    if args.print_urls:
        for u, ctx in result["urls"]:
            print(f"  [{ctx}] {u}")

    if args.fetch > 0 and result["urls"]:
        urls_only = [u for u, _ in result["urls"]]
        fetch_result = fetch_sample(urls_only, max_fetch=args.fetch)
        print(f"\nFetched {fetch_result['fetched']} articles:")
        for url, length in fetch_result["results"]:
            print(f"  {length:6} chars  {url[:70]}...")