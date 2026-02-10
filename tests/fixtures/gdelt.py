from datetime import datetime, timedelta, timezone
from typing import Dict, List


def create_mock_gdelt_event(
    eventid: str = "1234567890",
    eventcode: str = "190",
    category: str = "CONFLICT",
    lat: float = 40.0,
    lng: float = -74.0,
    actor1: str = "Actor1",
    actor2: str = "Actor2",
    actor1countrycode: str = "USA",
    actor2countrycode: str = "CHN",
    actiongeo: str = "New York, New York, United States",
    actiongeo_countrycode: str = "USA",
    date: str = None,
    importance: int = 10,
    sourceurl: str = "https://example.com/news1"
) -> Dict:
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {
            "eventid": eventid,
            "eventcode": eventcode,
            "category": category,
            "date": date,
            "name": f"{category}: {actor1}",
            "actor1": actor1,
            "actor2": actor2,
            "actor1countrycode": actor1countrycode,
            "actor2countrycode": actor2countrycode,
            "actiongeo": actiongeo,
            "actiongeo_countrycode": actiongeo_countrycode,
            "importance": importance,
            "sourceurl": sourceurl,
            "sources": [{"url": sourceurl, "type": "article", "name": "GDELT Source"}],
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "color": "#f97316"
        }
    }


def create_mock_bilateral_event(
    eventid: str = "1234567890",
    eventcode: str = "01",
    actor1countrycode: str = "USA",
    actor2countrycode: str = "CHN",
    lat: float = 40.0,
    lng: float = -74.0,
    importance: int = 15,
    date: str = None
) -> Dict:
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
    return create_mock_gdelt_event(
        eventid=eventid,
        eventcode=eventcode,
        category="OTHER",
        lat=lat,
        lng=lng,
        actor1=f"Actor from {actor1countrycode}",
        actor2=f"Actor from {actor2countrycode}",
        actor1countrycode=actor1countrycode,
        actor2countrycode=actor2countrycode,
        actiongeo=f"Location between {actor1countrycode} and {actor2countrycode}",
        actiongeo_countrycode=actor1countrycode,
        importance=importance,
        date=date
    )
