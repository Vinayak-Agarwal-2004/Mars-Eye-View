import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def temp_checkpoint_file(tmp_path):
    return tmp_path / "test_checkpoint.json"


@pytest.fixture
def temp_conflict_db(tmp_path):
    return tmp_path / "test_conflicts.duckdb"


@pytest.fixture
def temp_diplomacy_db(tmp_path):
    return tmp_path / "test_diplomacy.duckdb"


@pytest.fixture
def temp_alert_file(tmp_path):
    return tmp_path / "test_alerts.json"


@pytest.fixture
def mock_event_collection():
    from tests.fixtures import create_mock_event_collection
    return create_mock_event_collection
