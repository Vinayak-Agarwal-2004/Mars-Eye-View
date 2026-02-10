import pytest

from ingestion_engine.diplomatic_tracker import DiplomaticRelationsTracker
from tests.fixtures import create_mock_bilateral_event, create_mock_event_collection

pytestmark = pytest.mark.integration


class TestDiplomaticTracker:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.test_db = tmp_path / "test_diplomacy.duckdb"
        self.tracker = DiplomaticRelationsTracker(db_path=str(self.test_db))

    def test_bilateral_filtering(self):
        bilateral_event = create_mock_bilateral_event(
            eventid="1",
            actor1countrycode="USA",
            actor2countrycode="CHN"
        )
        domestic_event = create_mock_bilateral_event(
            eventid="2",
            actor1countrycode="USA",
            actor2countrycode="USA"
        )
        filtered = self.tracker.filter_bilateral_events([bilateral_event, domestic_event])
        assert len(filtered) == 1
        assert filtered[0]['properties']['actor1countrycode'] == "USA"
        assert filtered[0]['properties']['actor2countrycode'] == "CHN"

    def test_interaction_categorization(self):
        events = [
            create_mock_bilateral_event(eventid="1", eventcode="01", actor1countrycode="USA", actor2countrycode="CHN"),
            create_mock_bilateral_event(eventid="2", eventcode="15", actor1countrycode="USA", actor2countrycode="RUS"),
            create_mock_bilateral_event(eventid="3", eventcode="18", actor1countrycode="RUS", actor2countrycode="UKR"),
        ]
        bilateral = self.tracker.filter_bilateral_events(events)
        categorized = self.tracker.categorize_interactions(bilateral)
        assert len(categorized) == 3
        interaction_types = [e['interaction_type'] for e in categorized]
        assert 'diplomatic' in interaction_types
        assert 'military' in interaction_types
        assert 'conflict' in interaction_types

    def test_relation_metrics(self):
        events = [
            create_mock_bilateral_event(eventid="1", eventcode="01", actor1countrycode="USA", actor2countrycode="CHN"),
            create_mock_bilateral_event(eventid="2", eventcode="01", actor1countrycode="USA", actor2countrycode="CHN"),
            create_mock_bilateral_event(eventid="3", eventcode="18", actor1countrycode="USA", actor2countrycode="CHN"),
        ]
        bilateral = self.tracker.filter_bilateral_events(events)
        categorized = self.tracker.categorize_interactions(bilateral)
        relations = self.tracker.compute_relation_metrics(categorized)
        assert len(relations) > 0
        usa_chn = [r for r in relations if r['country_pair'] == 'CHN-USA']
        if usa_chn:
            relation = usa_chn[0]
            assert 'total_interactions' in relation
            assert 'cooperation_events' in relation
            assert 'conflict_events' in relation
            assert 'relation_trend' in relation

    def test_escalation_tracking(self):
        events = [
            create_mock_bilateral_event(eventid="1", eventcode="13", actor1countrycode="USA", actor2countrycode="RUS"),
            create_mock_bilateral_event(eventid="2", eventcode="15", actor1countrycode="USA", actor2countrycode="RUS"),
            create_mock_bilateral_event(eventid="3", eventcode="18", actor1countrycode="USA", actor2countrycode="RUS"),
        ]
        bilateral = self.tracker.filter_bilateral_events(events)
        categorized = self.tracker.categorize_interactions(bilateral)
        escalation = self.tracker.track_war_indicators(categorized)
        assert isinstance(escalation, list)
        if escalation:
            assert 'risk_score' in escalation[0]
            assert 'country_pair' in escalation[0]

    def test_database_storage(self):
        events = [
            create_mock_bilateral_event(eventid="1", actor1countrycode="USA", actor2countrycode="CHN"),
            create_mock_bilateral_event(eventid="2", actor1countrycode="USA", actor2countrycode="RUS"),
        ]
        bilateral = self.tracker.filter_bilateral_events(events)
        categorized = self.tracker.categorize_interactions(bilateral)
        self.tracker.store_interactions(categorized)
        count = self.tracker.db.execute("SELECT COUNT(*) FROM country_interactions").fetchone()[0]
        assert count >= len(categorized)

    def test_network_centrality_query(self):
        events = create_mock_event_collection(count=10, event_type="bilateral")
        bilateral = self.tracker.filter_bilateral_events(events)
        categorized = self.tracker.categorize_interactions(bilateral)
        self.tracker.store_interactions(categorized)
        centrality = self.tracker.query_network_centrality(days=30)
        assert isinstance(centrality, list)

    def test_conflict_pairs_query(self):
        events = [
            create_mock_bilateral_event(eventid="1", eventcode="18", actor1countrycode="USA", actor2countrycode="RUS"),
            create_mock_bilateral_event(eventid="2", eventcode="19", actor1countrycode="USA", actor2countrycode="RUS"),
            create_mock_bilateral_event(eventid="3", eventcode="20", actor1countrycode="USA", actor2countrycode="RUS"),
        ]
        bilateral = self.tracker.filter_bilateral_events(events)
        categorized = self.tracker.categorize_interactions(bilateral)
        self.tracker.store_interactions(categorized)
        conflict_pairs = self.tracker.query_conflict_pairs(days=30)
        assert isinstance(conflict_pairs, list)

    def test_country_pair_ordering(self):
        event1 = create_mock_bilateral_event(
            eventid="1",
            actor1countrycode="USA",
            actor2countrycode="CHN"
        )
        event2 = create_mock_bilateral_event(
            eventid="2",
            actor1countrycode="CHN",
            actor2countrycode="USA"
        )
        bilateral = self.tracker.filter_bilateral_events([event1, event2])
        categorized = self.tracker.categorize_interactions(bilateral)
        pairs = [e['country_pair'] for e in categorized]
        assert all(pair == 'CHN-USA' for pair in pairs)

    def test_process_events(self):
        events = create_mock_event_collection(count=10, event_type="bilateral")
        result = self.tracker.process_events(events)
        assert 'total_bilateral' in result
        assert 'categorized' in result
        assert 'relations_count' in result
        assert 'significant_developments' in result
        assert 'escalation_risks' in result

    def test_significant_developments(self):
        events = [
            create_mock_bilateral_event(eventid="1", eventcode="19", actor1countrycode="USA", actor2countrycode="RUS", importance=20),
            create_mock_bilateral_event(eventid="2", eventcode="01", actor1countrycode="USA", actor2countrycode="CHN", importance=5),
        ]
        bilateral = self.tracker.filter_bilateral_events(events)
        categorized = self.tracker.categorize_interactions(bilateral)
        significant = self.tracker.detect_significant_developments(categorized)
        assert isinstance(significant, list)
        if significant:
            assert 'priority_score' in significant[0]
