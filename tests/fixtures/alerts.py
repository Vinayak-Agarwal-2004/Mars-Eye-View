from datetime import datetime, timezone
from typing import Dict


def create_mock_alert(
    severity: float = 50.0,
    category: str = "violence",
    location: str = "Test Location",
    event_id: str = "1234567890"
) -> Dict:
    return {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event_id': event_id,
        'category': category,
        'severity': severity,
        'location': location,
        'country': 'USA',
        'description': f"Test {category} event",
        'goldstein': -8.0,
        'sources': 20,
        'tone': -5.0,
        'url': 'https://example.com/news'
    }


def create_mock_anomaly(
    location: str = "Test City",
    z_score: float = 3.5,
    current_count: int = 50,
    baseline_mean: float = 10.0
) -> Dict:
    return {
        "location": location,
        "grid_key": "40:-74",
        "current_count": current_count,
        "baseline_mean": baseline_mean,
        "baseline_std": 2.0,
        "z_score": z_score,
        "severity": "critical" if z_score > 4 else "high" if z_score > 3 else "elevated",
        "percent_above_normal": ((current_count - baseline_mean) / max(baseline_mean, 1) * 100),
        "top_sources": [{"url": "https://example.com", "count": 5}]
    }
