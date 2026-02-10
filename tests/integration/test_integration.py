import json
from datetime import datetime, timezone

import pytest

from server.app.services.checkpoint import CheckpointManager
from server.app.services.alerting import AlertingService
from ingestion_engine.conflict_monitor import ConflictMonitor
from ingestion_engine.diplomatic_tracker import DiplomaticRelationsTracker
from tests.fixtures import create_mock_event_collection, create_mock_alert

pytestmark = pytest.mark.integration


class TestIntegration:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.test_checkpoint = tmp_path / "test_checkpoint.json"
        self.test_conflict_db = tmp_path / "test_conflicts.duckdb"
        self.test_diplomacy_db = tmp_path / "test_diplomacy.duckdb"
        self.test_alert_file = tmp_path / "test_alerts.json"

    def test_firehose_integration(self):
        checkpoint = CheckpointManager(checkpoint_file=str(self.test_checkpoint))
        now = datetime.now(timezone.utc)
        checkpoint.save_checkpoint(now, processed_count=100)
        loaded = checkpoint.load_checkpoint()
        assert loaded is not None
        state = checkpoint.get_state()
        assert state['processed_count'] == 100

    def test_conflict_processing_integration(self):
        events = create_mock_event_collection(count=10, event_type="conflict")
        monitor = ConflictMonitor(db_path=str(self.test_conflict_db))
        result = monitor.process_events(events)
        assert 'total_conflict_events' in result
        assert 'alerts' in result
        if result['alerts']:
            alerting = AlertingService()
            alerting.alert_file = str(self.test_alert_file)
            alerting.send_alert(result['alerts'], source="conflict_monitor")
            assert self.test_alert_file.exists()

    def test_diplomatic_processing_integration(self):
        events = create_mock_event_collection(count=10, event_type="bilateral")
        tracker = DiplomaticRelationsTracker(db_path=str(self.test_diplomacy_db))
        result = tracker.process_events(events)
        assert 'total_bilateral' in result
        assert 'relations_count' in result
        if result.get('top_escalation'):
            alerting = AlertingService()
            alerting.alert_file = str(self.test_alert_file)
            escalation_alerts = [
                {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'category': 'escalation',
                    'severity': e.get('risk_score', 0),
                    'location': e.get('country_pair', 'Unknown'),
                    'description': f"Escalation risk: {e.get('risk_score', 0)}",
                    'url': ''
                }
                for e in result['top_escalation'][:3]
            ]
            alerting.send_alert(escalation_alerts, source="diplomatic_tracker")
            assert self.test_alert_file.exists()

    def test_end_to_end_pipeline(self):
        events = create_mock_event_collection(count=20, event_type="gdelt")
        checkpoint = CheckpointManager(checkpoint_file=str(self.test_checkpoint))
        conflict_monitor = ConflictMonitor(db_path=str(self.test_conflict_db))
        diplomatic_tracker = DiplomaticRelationsTracker(db_path=str(self.test_diplomacy_db))
        alerting = AlertingService()
        alerting.alert_file = str(self.test_alert_file)

        conflict_result = conflict_monitor.process_events(events)
        diplomacy_result = diplomatic_tracker.process_events(events)

        if conflict_result['alerts']:
            alerting.send_alert(conflict_result['alerts'], source="conflict_monitor")

        checkpoint.save_checkpoint(
            datetime.now(timezone.utc),
            processed_count=len(events),
            metadata={
                'conflict_events': conflict_result['total_conflict_events'],
                'bilateral_events': diplomacy_result['total_bilateral']
            }
        )

        assert conflict_result['total_conflict_events'] > 0
        assert diplomacy_result['total_bilateral'] > 0
        assert self.test_checkpoint.exists()

    def test_error_handling(self):
        checkpoint = CheckpointManager(checkpoint_file=str(self.test_checkpoint))
        missing_timestamp = checkpoint.load_checkpoint()
        assert missing_timestamp is not None

        conflict_monitor = ConflictMonitor(db_path=str(self.test_conflict_db))
        result = conflict_monitor.process_events([])
        assert result['total_conflict_events'] == 0

        diplomatic_tracker = DiplomaticRelationsTracker(db_path=str(self.test_diplomacy_db))
        result = diplomatic_tracker.process_events([])
        assert result['total_bilateral'] == 0

    def test_checkpoint_with_metadata(self):
        checkpoint = CheckpointManager(checkpoint_file=str(self.test_checkpoint))
        metadata = {
            'conflict_events': 10,
            'bilateral_events': 5,
            'alerts_generated': 3
        }
        checkpoint.save_checkpoint(
            datetime.now(timezone.utc),
            processed_count=15,
            metadata=metadata
        )
        state = checkpoint.get_state()
        assert state['metadata'] == metadata

    def test_alert_threshold_filtering(self):
        alerting = AlertingService()
        alerting.alert_file = str(self.test_alert_file)
        alerting.alert_threshold = 50.0

        alerts = [
            create_mock_alert(severity=75.0),
            create_mock_alert(severity=45.0),
            create_mock_alert(severity=60.0),
        ]
        alerting.send_alert(alerts, source="test")

        if self.test_alert_file.exists():
            with open(self.test_alert_file, 'r') as f:
                saved = json.load(f)
            saved_severities = [a.get('severity', 0) for a in saved.get('alerts', [])]
            if saved_severities:
                assert all(s > 50.0 for s in saved_severities)
