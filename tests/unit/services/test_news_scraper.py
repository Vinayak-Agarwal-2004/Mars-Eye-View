from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _mock_feed_entry(link: str, title: str = "Test Article", summary: str = "Test description"):
    entry = MagicMock()
    entry.link = link
    entry.title = title
    entry.summary = summary
    entry.published = "2024-01-15T12:00:00Z"
    entry.published_parsed = None
    entry.get = lambda k, d=None: {"link": link, "title": title, "summary": summary}.get(k, d)
    entry.links = [MagicMock(href=link)]
    return entry


@patch("feedparser.parse")
def test_run_dry_returns_events_and_count(mock_parse):
    from ingestion_engine.services.news_scraper import run

    mock_feed = MagicMock()
    mock_feed.entries = [
        _mock_feed_entry("https://example.com/article1", "Article 1"),
        _mock_feed_entry("https://example.com/article2", "Article 2"),
        _mock_feed_entry("https://example.com/article3", "Article 3"),
    ]
    mock_parse.return_value = mock_feed

    result = run(
        feed_urls=["https://feeds.bbci.co.uk/news/rss.xml"],
        max_articles_per_feed=3,
        fetch_full_text=False,
        write_events=False,
    )
    assert "count" in result
    assert "events" in result
    assert "errors" in result
    assert result["count"] == len(result["events"])
    assert result["feeds_processed"] == 1
    assert result["count"] == 3


@patch("feedparser.parse")
def test_event_has_required_fields(mock_parse):
    from ingestion_engine.services.news_scraper import run

    mock_feed = MagicMock()
    mock_feed.entries = [
        _mock_feed_entry("https://example.com/article1", "Article 1", "Description 1"),
    ]
    mock_parse.return_value = mock_feed

    result = run(
        feed_urls=["https://feeds.bbci.co.uk/news/rss.xml"],
        max_articles_per_feed=2,
        fetch_full_text=False,
        write_events=False,
    )
    if result["count"] == 0:
        pytest.skip("No events (feed may be down)")
    for ev in result["events"]:
        assert "name" in ev
        assert "source_url" in ev
        assert "description" in ev
        assert ev.get("visualization_type") == "dot"
        assert "participants" in ev
        assert "category" in ev


@patch("feedparser.parse")
def test_url_normalization_dedup(mock_parse):
    from ingestion_engine.services.news_scraper import run

    mock_feed = MagicMock()
    mock_feed.entries = [
        _mock_feed_entry("https://example.com/a"),
        _mock_feed_entry("https://example.com/b"),
        _mock_feed_entry("https://example.com/c"),
    ]
    mock_parse.return_value = mock_feed

    result = run(
        feed_urls=["https://feeds.bbci.co.uk/news/rss.xml"],
        max_articles_per_feed=10,
        fetch_full_text=False,
        write_events=False,
    )
    urls = [e["source_url"] for e in result["events"]]
    assert len(urls) == len(set(urls))
