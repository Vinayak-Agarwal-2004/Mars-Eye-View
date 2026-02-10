import pytest

from ingestion_engine.conflict_monitor import ConflictMonitor
from tests.fixtures import create_mock_conflict_event, create_mock_event_collection

pytestmark = pytest.mark.integration


class TestConflictMonitor:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.temp_dir = tmp_path
        self.test_db = tmp_path / "test_conflicts.duckdb"
        self.monitor = ConflictMonitor(db_path=str(self.test_db))

    def test_event_categorization(self):
        events = [
            create_mock_conflict_event(eventid="1", eventcode="141", category="protest"),
            create_mock_conflict_event(eventid="2", eventcode="190", category="violence"),
            create_mock_conflict_event(eventid="3", eventcode="173", category="coercion"),
        ]
        categorized = self.monitor.categorize_and_filter(events)
        assert len(categorized) == 3
        categories = [e['event_category'] for e in categorized]
        assert 'protest' in categories
        assert 'violence' in categories
        assert 'coercion' in categories

    def test_severity_score_calculation(self):
        event = create_mock_conflict_event(
            eventid="1",
            eventcode="190",
            category="violence",
            importance=30
        )
        categorized = self.monitor.categorize_and_filter([event])
        assert len(categorized) == 1
        severity = categorized[0]['severity_score']
        assert severity > 0
        assert isinstance(severity, (int, float))

    def test_high_impact_detection(self):
        events = [
            create_mock_conflict_event(eventid="1", eventcode="190", importance=50),
            create_mock_conflict_event(eventid="2", eventcode="141", importance=5),
            create_mock_conflict_event(eventid="3", eventcode="20", importance=100),
        ]
        categorized = self.monitor.categorize_and_filter(events)
        high_impact = self.monitor.detect_high_impact_events(categorized)
        assert len(high_impact) > 0
        assert len(high_impact) <= len(categorized)

    def test_database_storage(self):
        events = [
            create_mock_conflict_event(eventid="1", eventcode="190"),
            create_mock_conflict_event(eventid="2", eventcode="141"),
        ]
        categorized = self.monitor.categorize_and_filter(events)
        self.monitor.store_events(categorized)
        count = self.monitor.db.execute("SELECT COUNT(*) FROM conflict_events").fetchone()[0]
        assert count >= len(categorized)

    def test_query_protests(self):
        events = [
            create_mock_conflict_event(eventid="1", eventcode="141", category="protest", importance=15),
            create_mock_conflict_event(eventid="2", eventcode="141", category="protest", importance=5),
        ]
        categorized = self.monitor.categorize_and_filter(events)
        self.monitor.store_events(categorized)
        protests = self.monitor.query_protests(days=7, min_sources=10)
        assert isinstance(protests, list)

    def test_query_mass_casualty(self):
        events = [
            create_mock_conflict_event(eventid="1", eventcode="190", category="violence"),
            create_mock_conflict_event(eventid="2", eventcode="20", category="violence"),
        ]
        categorized = self.monitor.categorize_and_filter(events)
        self.monitor.store_events(categorized)
        casualties = self.monitor.query_mass_casualty(days=7)
        assert isinstance(casualties, list)

    def test_query_hotspots(self):
        events = create_mock_event_collection(count=10, event_type="conflict")
        categorized = self.monitor.categorize_and_filter(events)
        self.monitor.store_events(categorized)
        hotspots = self.monitor.query_hotspots(days=7)
        assert isinstance(hotspots, list)

    def test_camero_code_filtering(self):
        protest_event = create_mock_conflict_event(eventid="1", eventcode="141")
        violence_event = create_mock_conflict_event(eventid="2", eventcode="190")
        coercion_event = create_mock_conflict_event(eventid="3", eventcode="173")
        other_event = create_mock_conflict_event(eventid="4", eventcode="01")
        categorized = self.monitor.categorize_and_filter([
            protest_event, violence_event, coercion_event, other_event
        ])
        assert len(categorized) > 0
        categories = [e['event_category'] for e in categorized]
        assert 'protest' in categories
        assert 'violence' in categories
        assert 'coercion' in categories

    def test_process_events(self):
        events = create_mock_event_collection(count=5, event_type="conflict")
        result = self.monitor.process_events(events)
        assert 'total_conflict_events' in result
        assert 'high_impact_count' in result
        assert 'alerts' in result
        assert result['total_conflict_events'] >= 0
