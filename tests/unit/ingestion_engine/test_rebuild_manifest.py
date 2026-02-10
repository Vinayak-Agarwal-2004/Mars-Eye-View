import json
from pathlib import Path

import pytest

from ingestion_engine.maintenance import rebuild_manifest as rm

pytestmark = pytest.mark.unit


def test_rebuild_manifest_groups_interactions_by_category(tmp_path):
    interactions_dir = tmp_path / "interactions"
    disputes_dir = interactions_dir / "disputes"
    trade_dir = interactions_dir / "trade"
    disputes_dir.mkdir(parents=True)
    trade_dir.mkdir(parents=True)

    (disputes_dir / "dispute_1.json").write_text(
        json.dumps(
            {
                "id": "dispute_1",
                "name": "Border dispute",
                "description": "Sample dispute",
                "subtype": "territorial",
                "claimants": [{"iso": "IND"}, {"iso": "CHN"}],
            }
        ),
        encoding="utf-8",
    )

    (trade_dir / "trade_1.json").write_text(
        json.dumps(
            {
                "id": "trade_1",
                "name": "Trade deal",
                "description": "Sample trade agreement",
                "subtype": "Deal",
                "participants": ["USA", "CAN"],
            }
        ),
        encoding="utf-8",
    )

    original_interactions_dir = rm.INTERACTIONS_DIR
    original_manifest_path = rm.MANIFEST_PATH

    try:
        rm.INTERACTIONS_DIR = interactions_dir
        rm.MANIFEST_PATH = tmp_path / "manifest.json"

        rm.rebuild()

        manifest_path = Path(rm.MANIFEST_PATH)
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert "disputes" in manifest["byCategory"]
        assert "trade" in manifest["byCategory"]
        assert manifest["byCategory"]["disputes"] == ["dispute_1"]
        assert manifest["byCategory"]["trade"] == ["trade_1"]

        d_entry = manifest["interactionsById"]["dispute_1"]
        t_entry = manifest["interactionsById"]["trade_1"]

        assert d_entry["category"] == "disputes"
        assert t_entry["category"] == "trade"

        assert d_entry["subtype"] == "territorial"
        assert t_entry["subtype"] == "deal"
        assert t_entry["type_label"].lower().startswith("trade")
    finally:
        rm.INTERACTIONS_DIR = original_interactions_dir
        rm.MANIFEST_PATH = original_manifest_path
