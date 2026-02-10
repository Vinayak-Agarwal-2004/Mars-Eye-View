"""Configuration for manifest and interactions pipeline."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
INTERACTIONS_DIR = DATA_DIR / "interactions"

CONFIDENCE_THRESHOLD_HIGH = float(os.environ.get("INTERACTIONS_CONFIDENCE_HIGH", "0.7"))
CONFIDENCE_THRESHOLD_LOW = float(os.environ.get("INTERACTIONS_CONFIDENCE_LOW", "0.4"))
LAZY_LOAD_ANALYSIS = os.environ.get("INTERACTIONS_LAZY_LOAD", "true").lower() == "true"

RAW_LLM_EVENTS = INTERACTIONS_DIR / "raw_llm_events.json"
RAW_NEWS_EVENTS = INTERACTIONS_DIR / "raw_news_events.json"
MANIFEST_PATH = INTERACTIONS_DIR / "manifest.json"

DEFAULT_VISUALIZATION_TYPE = "geodesic"
DEFAULT_ARC_STYLE = "solid"
DEFAULT_TOAST_TYPE = "info"

TOAST_MESSAGE_TEMPLATE = "{name}: {type}"

RSS_FEED_URLS = [
    u.strip() for u in os.environ.get("NEWSPAPER_RSS_FEEDS", "").split(",") if u.strip()
] or [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
]

NEWS_SCRAPER_TIMEOUT = int(os.environ.get("NEWS_SCRAPER_TIMEOUT", "20"))
NEWS_SCRAPER_DELAY_SEC = float(os.environ.get("NEWS_SCRAPER_DELAY_SEC", "1.0"))
NEWS_SCRAPER_MAX_RETRIES = int(os.environ.get("NEWS_SCRAPER_MAX_RETRIES", "2"))
NEWS_SCRAPER_USE_NEWSPAPER3K = os.environ.get("NEWS_SCRAPER_USE_NEWSPAPER3K", "true").lower() == "true"

GDELT_LLM_MAX_PER_RUN = int(os.environ.get("GDELT_LLM_MAX_PER_RUN", "0"))
GDELT_LLM_DELAY_SEC = float(os.environ.get("GDELT_LLM_DELAY_SEC", "0"))
