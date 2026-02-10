import json
from pathlib import Path
from datetime import datetime, timedelta, timezone


class CheckpointManager:
    def __init__(self, checkpoint_file: str = "checkpoints/pipeline_state.json"):
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, timestamp: datetime, processed_count: int = 0, metadata: dict = None):
        state = {
            'last_timestamp': timestamp.isoformat(),
            'processed_count': processed_count,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        if metadata:
            state['metadata'] = metadata
        
        self.checkpoint_file.write_text(json.dumps(state, indent=2))
        return state

    def load_checkpoint(self) -> datetime:
        if not self.checkpoint_file.exists():
            return datetime.now(timezone.utc) - timedelta(days=1)
        
        try:
            state = json.loads(self.checkpoint_file.read_text())
            return datetime.fromisoformat(state['last_timestamp'])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[Checkpoint] Load failed: {e}, using default")
            return datetime.now(timezone.utc) - timedelta(days=1)

    def get_state(self) -> dict:
        if not self.checkpoint_file.exists():
            return {
                'last_timestamp': None,
                'processed_count': 0,
                'updated_at': None
            }
        
        try:
            return json.loads(self.checkpoint_file.read_text())
        except (json.JSONDecodeError, KeyError, ValueError):
            return {
                'last_timestamp': None,
                'processed_count': 0,
                'updated_at': None
            }

    def update_processed_count(self, count: int):
        state = self.get_state()
        state['processed_count'] = state.get('processed_count', 0) + count
        state['updated_at'] = datetime.now(timezone.utc).isoformat()
        self.checkpoint_file.write_text(json.dumps(state, indent=2))
        return state
