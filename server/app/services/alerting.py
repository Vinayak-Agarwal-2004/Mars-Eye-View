import os
import json
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional


class AlertingService:
    def __init__(self):
        self.telegram_webhook = os.getenv("TELEGRAM_WEBHOOK_URL")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        self.alert_threshold = float(os.getenv("ALERT_SEVERITY_THRESHOLD", "50.0"))
        self.alert_file = "data/live/alerts_latest.json"

    def send_alert(self, alerts: List[Dict], source: str = "conflict_monitor"):
        if not alerts:
            return
        
        high_severity = [a for a in alerts if a.get('severity', 0) > self.alert_threshold]
        
        if not high_severity:
            return
        
        message = self._format_alerts(high_severity, source)
        
        if self.telegram_webhook:
            self._send_telegram(message)
        
        if self.discord_webhook:
            self._send_discord(message)
        
        self._save_alerts(high_severity)

    def _format_alerts(self, alerts: List[Dict], source: str) -> str:
        lines = [f"🚨 {len(alerts)} HIGH-IMPACT EVENTS DETECTED ({source})"]
        lines.append("=" * 50)
        
        for alert in alerts[:10]:
            category = alert.get('category', 'unknown').upper()
            location = alert.get('location', 'Unknown')
            severity = alert.get('severity', 0)
            desc = alert.get('description', 'No description')
            
            lines.append(f"\n[{category}] {location}")
            lines.append(f"  Severity: {severity:.1f}")
            lines.append(f"  {desc}")
            if alert.get('url'):
                lines.append(f"  Source: {alert['url']}")
        
        if len(alerts) > 10:
            lines.append(f"\n... and {len(alerts) - 10} more events")
        
        return "\n".join(lines)

    def _send_telegram(self, message: str):
        if not self.telegram_webhook:
            return
        
        try:
            payload = {
                "text": message,
                "parse_mode": "HTML"
            }
            resp = requests.post(self.telegram_webhook, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Alerting] Telegram send failed: {e}")

    def _send_discord(self, message: str):
        if not self.discord_webhook:
            return
        
        try:
            payload = {
                "content": message[:2000]
            }
            resp = requests.post(self.discord_webhook, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Alerting] Discord send failed: {e}")

    def _save_alerts(self, alerts: List[Dict]):
        try:
            alert_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(alerts),
                "alerts": alerts
            }
            os.makedirs(os.path.dirname(self.alert_file), exist_ok=True)
            with open(self.alert_file, 'w') as f:
                json.dump(alert_data, f, indent=2)
        except Exception as e:
            print(f"[Alerting] Save failed: {e}")

    def send_anomaly_alert(self, anomalies: List[Dict]):
        if not anomalies:
            return
        
        critical = [a for a in anomalies if a.get('severity') == 'critical']
        
        if critical:
            message = self._format_anomalies(critical)
            if self.telegram_webhook:
                self._send_telegram(message)
            if self.discord_webhook:
                self._send_discord(message)

    def _format_anomalies(self, anomalies: List[Dict]) -> str:
        lines = [f"⚠️ {len(anomalies)} CRITICAL ANOMALIES DETECTED"]
        lines.append("=" * 50)
        
        for anomaly in anomalies[:10]:
            location = anomaly.get('location', 'Unknown')
            z_score = anomaly.get('z_score', 0)
            current = anomaly.get('current_count', 0)
            baseline = anomaly.get('baseline_mean', 0)
            pct = anomaly.get('percent_above_normal', 0)
            
            lines.append(f"\n📍 {location}")
            lines.append(f"  Z-Score: {z_score:.2f}")
            lines.append(f"  Current: {current} (baseline: {baseline:.1f}, +{pct:.1f}%)")
        
        return "\n".join(lines)
