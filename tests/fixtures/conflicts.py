from tests.fixtures.gdelt import create_mock_gdelt_event


def create_mock_conflict_event(
    eventid: str = "1234567890",
    eventcode: str = "190",
    category: str = "violence",
    lat: float = 40.0,
    lng: float = -74.0,
    actor1: str = "Actor1",
    actor2: str = "Actor2",
    importance: int = 20,
    date: str = None
) -> dict:
    from datetime import datetime, timezone
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
    cat_map = {"violence": "VIOLENCE", "protest": "PROTEST", "coercion": "CONFLICT"}
    category_upper = cat_map.get(category, "CONFLICT")
    return create_mock_gdelt_event(
        eventid=eventid,
        eventcode=eventcode,
        category=category_upper,
        lat=lat,
        lng=lng,
        actor1=actor1,
        actor2=actor2,
        importance=importance,
        date=date
    )
