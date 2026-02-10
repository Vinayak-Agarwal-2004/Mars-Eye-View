import copy
from datetime import datetime, timezone

import pytest

from ingestion_engine.streamers.gdelt_firehose import (
    attach_sources_to_features,
    prune_old_events,
)
from tests.fixtures import create_mock_gdelt_event

pytestmark = pytest.mark.unit


def _today_yyyymmdd():
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def test_attach_sources_combines_primary_and_mentions():
    event_id = "E1"
    primary_url = "https://primary.example.com/article"
    feat = create_mock_gdelt_event(eventid=event_id, sourceurl=primary_url)
    feat["properties"].pop("sources", None)
    mention_map = {
        event_id: {
            "https://a.example.com/story",
            "https://b.example.com/report",
        }
    }
    out = attach_sources_to_features([feat], mention_map)
    props = out[0]["properties"]
    urls = {s["url"] for s in props.get("sources", [])}
    assert primary_url in urls
    assert "https://a.example.com/story" in urls
    assert "https://b.example.com/report" in urls
    assert len(urls) == 3


def test_attach_sources_handles_missing_mentions_gracefully():
    event_id = "E2"
    primary_url = "https://only-primary.example.com/article"
    feat = create_mock_gdelt_event(eventid=event_id, sourceurl=primary_url)
    feat["properties"].pop("sources", None)
    mention_map = {}
    out = attach_sources_to_features([feat], mention_map)
    props = out[0]["properties"]
    urls = [s["url"] for s in props.get("sources", [])]
    assert urls == [primary_url]


def test_prune_old_events_uses_eventid_not_name_coords_for_dedup():
    base = create_mock_gdelt_event(
        eventid="DEDUP_TEST",
        date=_today_yyyymmdd(),
        lat=10.0,
        lng=20.0,
    )
    modified = copy.deepcopy(base)
    modified["geometry"]["coordinates"] = [20.0, 10.0]
    modified["properties"]["name"] = "Modified name same eventid"
    out = prune_old_events([base, modified])
    assert len(out) == 1
    assert out[0]["properties"]["eventid"] == "DEDUP_TEST"


def test_prune_old_events_keeps_distinct_events_at_same_location():
    today = _today_yyyymmdd()
    a = create_mock_gdelt_event(
        eventid="E1",
        eventcode="190",
        lat=30.0,
        lng=50.0,
        date=today,
    )
    b = create_mock_gdelt_event(
        eventid="E2",
        eventcode="141",
        lat=30.0,
        lng=50.0,
        date=today,
    )
    out = prune_old_events([a, b])
    ids = {f["properties"]["eventid"] for f in out}
    assert ids == {"E1", "E2"}
