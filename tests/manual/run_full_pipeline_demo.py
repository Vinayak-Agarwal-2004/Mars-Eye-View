#!/usr/bin/env python3
"""Demo: Full pipeline with sample GDELT events. Standalone - no server required."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.app.services.checkpoint import CheckpointManager
from server.app.services.alerting import AlertingService
from ingestion_engine.conflict_monitor import ConflictMonitor
from ingestion_engine.diplomatic_tracker import DiplomaticRelationsTracker
from tests.fixtures import create_mock_event_collection


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main():
    print_section("Full Pipeline Demo")
    test_checkpoint = "checkpoints/test_integration_state.json"
    test_conflict_db = "data/test_integration_conflicts.duckdb"
    test_diplomacy_db = "data/test_integration_diplomacy.duckdb"
    test_alert_file = "data/live/test_integration_alerts.json"

    checkpoint = CheckpointManager(checkpoint_file=test_checkpoint)
    alerting = AlertingService()
    alerting.alert_file = test_alert_file
    conflict_monitor = ConflictMonitor(db_path=test_conflict_db)
    diplomatic_tracker = DiplomaticRelationsTracker(db_path=test_diplomacy_db)

    events = create_mock_event_collection(count=30, event_type="gdelt")
    conflict_result = conflict_monitor.process_events(events)
    diplomacy_result = diplomatic_tracker.process_events(events)

    escalation_alerts = []
    if conflict_result['alerts']:
        alerting.send_alert(conflict_result['alerts'], source="conflict_monitor")
    if diplomacy_result.get('top_escalation'):
        escalation_alerts = [
            {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'escalation',
                'severity': e.get('risk_score', 0),
                'location': e.get('country_pair', 'Unknown'),
                'description': f"Escalation risk: {e.get('risk_score', 0)}",
                'url': ''
            }
            for e in diplomacy_result['top_escalation'][:3]
        ]
        alerting.send_alert(escalation_alerts, source="diplomatic_tracker")

    checkpoint.save_checkpoint(
        timestamp=datetime.now(timezone.utc),
        processed_count=len(events),
        metadata={
            'conflict_events': conflict_result['total_conflict_events'],
            'bilateral_events': diplomacy_result['total_bilateral'],
            'alerts_generated': len(conflict_result['alerts']) + len(escalation_alerts)
        }
    )

    print(f"✓ Processed {len(events)} events")
    print(f"✓ Conflict: {conflict_result['total_conflict_events']}, Diplomacy: {diplomacy_result['total_bilateral']}")


if __name__ == '__main__':
    main()
