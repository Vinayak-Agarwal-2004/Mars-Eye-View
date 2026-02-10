# Test Suite

## Quick Start

```bash
# Single controller - run unit tests (default, fast)
python tests/run_tests.py

# Unit + integration
python tests/run_tests.py --tier integration

# Full suite (unit + integration + e2e)
python tests/run_tests.py --tier full

# With coverage
python tests/run_tests.py --tier integration --coverage

# CI mode (junit XML + coverage XML)
python tests/run_tests.py --ci

# Manual verification scripts
python tests/run_tests.py --tier manual
```

## Structure

```
tests/
├── run_tests.py              # Single controller
├── conftest.py               # Shared fixtures, path setup
├── fixtures/                 # Mock data (gdelt, conflicts, alerts)
├── unit/
│   ├── services/             # Checkpoint, alerting, news_scraper
│   └── ingestion_engine/     # Firehose join, rebuild manifest, transnational
├── integration/              # Conflict monitor, diplomatic tracker, full integration
├── e2e/                      # Advanced analytics (HotspotAnalyzer)
└── manual/                   # Verification scripts (many require server)
```

## Logic Flow

### conftest.py

Adds project root to sys.path so imports resolve. Provides fixtures: temp_checkpoint_file (tmp_path/test_checkpoint.json), temp_conflict_db, temp_diplomacy_db, temp_alert_file for isolated file/db paths; mock_event_collection (wrapper for create_mock_event_collection).

### fixtures/

**gdelt.py** – create_mock_gdelt_event returns GeoJSON Feature with geometry, properties (eventid, eventcode, category, actors, country codes, importance, sourceurl). create_mock_bilateral_event wraps it with distinct actor1/actor2 country codes for diplomatic tests.

**conflicts.py** – create_mock_conflict_event maps violence/protest/coercion to GDELT categories and delegates to create_mock_gdelt_event. Used by conflict_monitor tests.

**events.py** – create_mock_event_collection returns FeatureCollection of features for bulk tests.

**alerts.py** – create_mock_alert and create_mock_anomaly for alerting tests.

Fixture functions accept kwargs to override defaults; return shapes match what ConflictMonitor, DiplomaticTracker, and FirehoseService expect.

### unit/

**services/** – test_checkpoint: save/load/get_state/update_processed_count with temp file. test_alerting: format and send logic with mocked webhooks. test_news_scraper: scraper behavior with mocked network.

**ingestion_engine/** – test_gdelt_firehose_join: export+mentions join logic. test_rebuild_manifest: rebuild_manifest output structure. test_transnational_filtering: transnational filter (actor1 != actor2).

**test_sanity.py** – Basic smoke test.

### integration/

**test_conflict_monitor** – ConflictMonitor with temp DuckDB. Tests categorize_and_filter (protest/violence/coercion codes), severity calculation, high_impact detection, store_events, generate_alerts. Uses create_mock_conflict_event.

**test_diplomatic_tracker** – DiplomaticRelationsTracker with temp DuckDB. Tests filter_bilateral_events, categorize_interactions, store_interactions, compute_relation_metrics, store_bilateral_relations. Uses create_mock_bilateral_event.

**test_integration** – Full pipeline with FirehoseService, ConflictMonitor, DiplomaticTracker; checks end-to-end flow with mock data.

### e2e/

**test_full_pipeline** – HotspotAnalyzer with FirehoseService; uses live history_data or fixtures. Tests analyze, detect_anomalies. Slower; marked e2e.

### manual/

Scripts for ad-hoc verification. Most require server running on localhost:8000. analyze_live_data, verify_transnational, verify_transnational_dbscan, print_anomalies, print_dbscan_clusters, check_data_schema, debug_cleveland, verify_live_api. Standalone: run_full_pipeline_demo (mock events, no server), llm_full_dump_to_file. Run via `python tests/run_tests.py --tier manual` or directly `python tests/manual/<script>.py`.

### run_tests.py

Parses --tier (unit/integration/full/manual), --coverage, --ci, --parallel, --manual. unit: -m unit. integration: -m integration. full: -m "unit or integration or e2e". manual: runs manual scripts instead of pytest. Coverage adds --cov for server.app.services and ingestion_engine. CI adds junit XML and coverage XML outputs to reports/.

## Markers

- `unit` - Fast, isolated
- `integration` - Components together
- `e2e` - End-to-end, slower
- `slow` - Skip in quick runs
- `external` - Requires network

## Fixtures

`tests.fixtures` provides: `create_mock_gdelt_event`, `create_mock_conflict_event`, `create_mock_bilateral_event`, `create_mock_event_collection`, `create_mock_alert`, `create_mock_anomaly`.

## Direct pytest

```bash
pytest tests/ -v
pytest tests/unit/ -m unit
pytest tests/integration/ -m integration
pytest tests/ --cov=server.app.services --cov=ingestion_engine --cov-report=html
```
