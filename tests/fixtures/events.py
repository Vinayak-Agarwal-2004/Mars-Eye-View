from datetime import datetime, timedelta, timezone
from typing import Dict, List

from tests.fixtures.gdelt import create_mock_gdelt_event, create_mock_bilateral_event
from tests.fixtures.conflicts import create_mock_conflict_event


def create_mock_event_collection(count: int = 10, event_type: str = "gdelt") -> List[Dict]:
    events = []
    base_time = datetime.now(timezone.utc)
    for i in range(count):
        days_ago = i % 7
        date = (base_time - timedelta(days=days_ago)).strftime("%Y%m%d")
        if event_type == "conflict":
            category = ["violence", "protest", "coercion"][i % 3]
            event = create_mock_conflict_event(
                eventid=str(1234567890 + i),
                eventcode=["190", "141", "173"][i % 3],
                category=category,
                lat=40.0 + (i * 0.1),
                lng=-74.0 + (i * 0.1),
                importance=10 + i,
                date=date
            )
        elif event_type == "bilateral":
            event = create_mock_bilateral_event(
                eventid=str(1234567890 + i),
                eventcode=["01", "15", "18"][i % 3],
                actor1countrycode=["USA", "RUS", "CHN"][i % 3],
                actor2countrycode=["CHN", "USA", "RUS"][(i + 1) % 3],
                lat=40.0 + (i * 0.1),
                lng=-74.0 + (i * 0.1),
                importance=15 + i,
                date=date
            )
        else:
            event = create_mock_gdelt_event(
                eventid=str(1234567890 + i),
                eventcode=["190", "141", "173"][i % 3],
                lat=40.0 + (i * 0.1),
                lng=-74.0 + (i * 0.1),
                importance=10 + i,
                date=date
            )
        events.append(event)
    return events
