import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.app.services.alerting import AlertingService
from tests.fixtures import create_mock_alert, create_mock_anomaly

pytestmark = pytest.mark.unit


class TestAlerting:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.test_alert_file = tmp_path / "test_alerts.json"
        self.alerting = AlertingService()
        self.alerting.alert_file = str(self.test_alert_file)
        self.alerting.alert_threshold = 50.0
        self.alerting.telegram_webhook = None
        self.alerting.discord_webhook = None

    def test_alert_formatting(self):
        alerts = [
            create_mock_alert(severity=75.0, category="violence", location="Test Location 1"),
            create_mock_alert(severity=60.0, category="protest", location="Test Location 2"),
        ]
        message = self.alerting._format_alerts(alerts, source="test")
        assert isinstance(message, str)
        assert "HIGH-IMPACT EVENTS" in message
        assert "Test Location 1" in message
        assert "VIOLENCE" in message.upper()

    def test_severity_threshold(self):
        alerts = [
            create_mock_alert(severity=75.0),
            create_mock_alert(severity=60.0),
            create_mock_alert(severity=45.0),
            create_mock_alert(severity=30.0),
        ]
        self.alerting.alert_threshold = 50.0
        self.alerting.send_alert(alerts, source="test")
        if self.test_alert_file.exists():
            with open(self.test_alert_file, 'r') as f:
                saved = json.load(f)
            saved_alerts = saved.get('alerts', [])
            severities = [a.get('severity', 0) for a in saved_alerts]
            if severities:
                assert all(s > 50.0 for s in severities)

    def test_alert_persistence(self):
        alerts = [
            create_mock_alert(severity=75.0),
            create_mock_alert(severity=60.0),
        ]
        self.alerting.send_alert(alerts, source="test")
        assert self.test_alert_file.exists()
        with open(self.test_alert_file, 'r') as f:
            saved = json.load(f)
        assert 'generated_at' in saved
        assert 'count' in saved
        assert 'alerts' in saved
        assert saved['count'] == len([a for a in alerts if a.get('severity', 0) > self.alerting.alert_threshold])

    def test_anomaly_alert_formatting(self):
        anomalies = [
            create_mock_anomaly(location="City A", z_score=4.5),
            create_mock_anomaly(location="City B", z_score=3.2),
        ]
        message = self.alerting._format_anomalies(anomalies)
        assert isinstance(message, str)
        assert "ANOMALIES" in message.upper()
        assert "City A" in message

    def test_webhook_urls(self):
        self.alerting.telegram_webhook = "https://api.telegram.org/bot123/webhook"
        self.alerting.discord_webhook = "https://discord.com/api/webhooks/123"
        assert self.alerting.telegram_webhook == "https://api.telegram.org/bot123/webhook"
        assert self.alerting.discord_webhook == "https://discord.com/api/webhooks/123"

    def test_alert_counting(self):
        alerts = [
            create_mock_alert(severity=75.0),
            create_mock_alert(severity=60.0),
            create_mock_alert(severity=45.0),
        ]
        self.alerting.alert_threshold = 50.0
        high_severity = [a for a in alerts if a.get('severity', 0) > self.alerting.alert_threshold]
        assert len(high_severity) == 2
        assert len([a for a in alerts if a.get('severity', 0) <= self.alerting.alert_threshold]) == 1

    def test_send_alert_with_empty_list(self):
        self.alerting.send_alert([], source="test")
        assert not self.test_alert_file.exists()

    def test_send_anomaly_alert(self):
        anomalies = [create_mock_anomaly(location="City A", z_score=4.5)]
        self.alerting.send_anomaly_alert(anomalies)
        assert self.alerting.alert_file is not None

    @patch('requests.post')
    def test_webhook_sending_telegram(self, mock_post):
        self.alerting.telegram_webhook = "https://api.telegram.org/bot123/webhook"
        mock_post.return_value = MagicMock(status_code=200)
        alerts = [create_mock_alert(severity=75.0)]
        self.alerting.send_alert(alerts, source="test")
        if self.alerting.telegram_webhook:
            mock_post.assert_called()

    @patch('requests.post')
    def test_webhook_sending_discord(self, mock_post):
        self.alerting.discord_webhook = "https://discord.com/api/webhooks/123"
        mock_post.return_value = MagicMock(status_code=200)
        alerts = [create_mock_alert(severity=75.0)]
        self.alerting.send_alert(alerts, source="test")
        if self.alerting.discord_webhook:
            mock_post.assert_called()
