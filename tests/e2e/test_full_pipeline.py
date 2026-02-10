from datetime import datetime, timedelta, timezone

import pytest

from server.app.services.hotspot import HotspotAnalyzer

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class MockFirehose:
    def __init__(self):
        self.history_data = {"features": []}
        self.latest_hotspots = None


class TestAdvancedAnalytics:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.firehose = MockFirehose()
        self.analyzer = HotspotAnalyzer(self.firehose)
        self.now = datetime.now(timezone.utc)

    def _create_event(self, days_ago, lat, lng, name, actor1=None, actor2=None):
        ts = (self.now - timedelta(days=days_ago)).isoformat()
        return {
            "type": "Feature",
            "properties": {
                "ingested_at": ts,
                "name": name,
                "importance": 1,
                "actor1": actor1,
                "actor2": actor2,
                "eventcode": "190",
                "category": "CONFLICT"
            },
            "geometry": {"type": "Point", "coordinates": [lng, lat]}
        }

    def test_anomaly_detection_spike(self):
        events = []
        for d in range(1, 7):
            for _ in range(5):
                events.append(self._create_event(d, 40.0, -74.0, "Test City"))
        for _ in range(55):
            events.append(self._create_event(0, 40.0, -74.0, "Test City"))

        self.firehose.history_data["features"] = events
        result = self.analyzer.detect_anomalies(lookback_days=7, sigma_threshold=3.0)

        assert len(result["anomalies"]) > 0
        top = result["anomalies"][0]
        assert top["location"] == "Test City"
        assert top["z_score"] > 3.0
        assert top["severity"] == "critical"

    def test_actor_network_edges(self):
        events = []
        for _ in range(5):
            events.append(self._create_event(0, 0, 0, "Verona", "Romeo", "Juliet"))
        events.append(self._create_event(0, 0, 0, "Verona", "Romeo", "Mercutio"))

        self.firehose.history_data["features"] = events
        result = self.analyzer.build_actor_network(min_weight=3)
        edges = result["edges"]

        assert len(edges) == 1
        assert edges[0]["source"] == "juliet"
        assert edges[0]["target"] == "romeo"
        assert edges[0]["weight"] == 5

    def test_dbscan_clustering(self):
        pytest.importorskip("sklearn")

        events = []
        for i in range(5):
            events.append(self._create_event(0, 10.0 + i * 0.01, 10.0 + i * 0.01, "Cluster A"))
        for i in range(5):
            events.append(self._create_event(0, 20.0 + i * 0.01, 20.0 + i * 0.01, "Cluster B"))
        events.append(self._create_event(0, 50.0, 50.0, "Noise"))

        self.firehose.history_data["features"] = events
        result = self.analyzer.analyze(clustering_method="dbscan", dbscan_eps=500.0, dbscan_min_samples=2)

        clusters = result["hotspots"]["location"]
        assert len(clusters) >= 2
        assert clusters[0]["count"] == 5
