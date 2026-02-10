import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from server.app.services.checkpoint import CheckpointManager

pytestmark = pytest.mark.unit


class TestCheckpoint:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.temp_dir = tmp_path
        self.test_file = tmp_path / "test_checkpoint.json"
        self.checkpoint = CheckpointManager(checkpoint_file=str(self.test_file))

    def test_save_and_load_checkpoint(self):
        now = datetime.now(timezone.utc)
        saved_state = self.checkpoint.save_checkpoint(
            timestamp=now,
            processed_count=100
        )
        assert saved_state['processed_count'] == 100
        assert saved_state['last_timestamp'] is not None
        assert saved_state['updated_at'] is not None
        loaded_timestamp = self.checkpoint.load_checkpoint()
        assert loaded_timestamp is not None
        assert abs((loaded_timestamp - now).total_seconds()) < 1

    def test_checkpoint_metadata(self):
        metadata = {
            'test_key': 'test_value',
            'export_url': 'http://example.com/export.csv.zip'
        }
        saved_state = self.checkpoint.save_checkpoint(
            timestamp=datetime.now(timezone.utc),
            processed_count=50,
            metadata=metadata
        )
        assert 'metadata' in saved_state
        assert saved_state['metadata'] == metadata
        loaded_state = self.checkpoint.get_state()
        assert loaded_state['metadata'] == metadata

    def test_update_processed_count(self):
        self.checkpoint.save_checkpoint(
            timestamp=datetime.now(timezone.utc),
            processed_count=100
        )
        updated_state = self.checkpoint.update_processed_count(50)
        assert updated_state['processed_count'] == 150
        updated_state = self.checkpoint.update_processed_count(25)
        assert updated_state['processed_count'] == 175

    def test_crash_recovery(self):
        missing_checkpoint = CheckpointManager(
            checkpoint_file=str(self.temp_dir / "nonexistent.json")
        )
        default_timestamp = missing_checkpoint.load_checkpoint()
        assert default_timestamp is not None
        expected_default = datetime.now(timezone.utc) - timedelta(days=1)
        assert abs((default_timestamp - expected_default).total_seconds()) < 86400

    def test_checkpoint_file_creation(self):
        assert not self.test_file.exists()
        self.checkpoint.save_checkpoint(
            timestamp=datetime.now(timezone.utc),
            processed_count=10
        )
        assert self.test_file.exists()
        content = json.loads(self.test_file.read_text())
        assert 'last_timestamp' in content
        assert 'processed_count' in content

    def test_get_state_empty(self):
        empty_checkpoint = CheckpointManager(
            checkpoint_file=str(self.temp_dir / "empty.json")
        )
        state = empty_checkpoint.get_state()
        assert state['processed_count'] == 0
        assert state['last_timestamp'] is None

    def test_get_state_with_data(self):
        self.checkpoint.save_checkpoint(
            timestamp=datetime.now(timezone.utc),
            processed_count=200
        )
        state = self.checkpoint.get_state()
        assert state['processed_count'] == 200
        assert state['last_timestamp'] is not None
