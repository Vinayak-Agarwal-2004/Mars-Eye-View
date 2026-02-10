from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest

from server.app.services.hotspot import HotspotAnalyzer

pytestmark = pytest.mark.unit


class MockFirehose:
    def __init__(self, features):
        self.history_data = {"type": "FeatureCollection", "features": features}
        self.history_window_hours = 168
        self.hotspot_config = {"window_hours": 168, "previous_hours": 720, "grid_km": 120, "top": 10}

    def get_history(self, hours=168, transnational=False):
        filtered = []
        for f in self.history_data.get("features", []):
            if transnational:
                p = f.get("properties", {})
                a1 = p.get("actor1countrycode")
                a2 = p.get("actor2countrycode")
                if not a1 or not a2 or a1 == a2:
                    continue
            filtered.append(f)
        return {"features": filtered}


FIXED_TIME_STR = "2026-02-09T12:00:00+00:00"
FIXED_TIME = datetime.fromisoformat(FIXED_TIME_STR)


@pytest.fixture
def mock_features():
    return [
        {
            "type": "Feature",
            "properties": {
                "name": "Domestic Protests",
                "actor1countrycode": "USA",
                "actor2countrycode": "USA",
                "ingested_at": FIXED_TIME_STR,
                "eventcode": "140"
            },
            "geometry": {"type": "Point", "coordinates": [-77.0369, 38.9072]}
        },
        {
            "type": "Feature",
            "properties": {
                "name": "Trade Dispute",
                "actor1countrycode": "USA",
                "actor2countrycode": "CHN",
                "ingested_at": FIXED_TIME_STR,
                "eventcode": "190"
            },
            "geometry": {"type": "Point", "coordinates": [116.4074, 39.9042]}
        },
        {
            "type": "Feature",
            "properties": {
                "name": "US in Iraq",
                "actor1countrycode": "USA",
                "actor2countrycode": "IRQ",
                "ingested_at": FIXED_TIME_STR,
                "eventcode": "190"
            },
            "geometry": {"type": "Point", "coordinates": [44.3615, 33.3128]}
        }
    ]


@patch("server.app.services.hotspot.datetime")
def test_transnational_logic_dbscan(mock_dt, mock_features):
    mock_dt.now.return_value = FIXED_TIME
    mock_dt.fromisoformat = datetime.fromisoformat
    mock_dt.strptime = datetime.strptime
    mock_dt.timezone = timezone

    firehose = MockFirehose(mock_features)
    analyzer = HotspotAnalyzer(firehose)
    analyzer._build_dbscan_stats = MagicMock(return_value={"location": {}, "event": {}, "actor": {}})

    analyzer.analyze(clustering_method="dbscan")

    assert analyzer._build_dbscan_stats.call_count >= 1
    call_args = analyzer._build_dbscan_stats.call_args_list[0]
    passed_features = call_args[0][0]

    assert len(passed_features) == 2
    codes = [f["properties"]["actor2countrycode"] for f in passed_features]
    assert "CHN" in codes
    assert "IRQ" in codes
    assert "USA" not in codes


@patch("server.app.services.hotspot.datetime")
def test_transnational_logic_grid(mock_dt, mock_features):
    mock_dt.now.return_value = FIXED_TIME
    mock_dt.fromisoformat = datetime.fromisoformat
    mock_dt.strptime = datetime.strptime
    mock_dt.timezone = timezone

    firehose = MockFirehose(mock_features)
    analyzer = HotspotAnalyzer(firehose)
    analyzer._build_stats = MagicMock(return_value={"location": {}, "event": {}, "actor": {}})

    analyzer.analyze(clustering_method="grid")

    assert analyzer._build_stats.call_count >= 1
    call_args = analyzer._build_stats.call_args_list[0]
    passed_features = call_args[0][0]

    assert len(passed_features) == 3


def test_filtering_result(mock_features):
    firehose = MockFirehose(mock_features)
    analyzer = HotspotAnalyzer(firehose)
    filtered = [f for f in mock_features if analyzer._is_transnational(f)]

    assert len(filtered) == 2
    props = [f["properties"] for f in filtered]
    assert any(p["actor2countrycode"] == "CHN" for p in props)
    assert any(p["actor2countrycode"] == "IRQ" for p in props)


def test_anomalies_global(mock_features):
    firehose = MockFirehose(mock_features)
    analyzer = HotspotAnalyzer(firehose)

    import inspect
    sig = inspect.signature(analyzer.detect_anomalies)
    assert sig.parameters["transnational"].default is False


def test_timestamp_parsing(mock_features):
    firehose = MockFirehose(mock_features)
    analyzer = HotspotAnalyzer(firehose)

    feat = mock_features[0]
    ts = analyzer._get_ingested_at(feat)

    assert ts is not None
    assert ts == FIXED_TIME
