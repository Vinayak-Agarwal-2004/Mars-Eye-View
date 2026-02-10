# Manual Verification Scripts

Run from project root: `python tests/manual/<script>.py`

## Server Required (localhost:8000)

- `analyze_live_data.py` - Hotspots, anomalies, actor network
- `verify_transnational.py` - Transnational filtering check
- `verify_transnational_dbscan.py` - DBSCAN transnational logic
- `print_anomalies.py` - Anomaly display
- `print_dbscan_clusters.py` - DBSCAN cluster display
- `check_data_schema.py` - Event property inspection
- `debug_cleveland.py` - Domestic vs international debug
- `verify_live_api.py` - API health and endpoint checks

## Standalone

- `run_full_pipeline_demo.py` - Full pipeline with mock events (no server)
- `llm_full_dump_to_file.py` - LLM context dump utility
