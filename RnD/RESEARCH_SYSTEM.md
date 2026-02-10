# GDELT-Streamer Research Document

Date: 2026-02-03
Version: 1.0

## Abstract
This document describes the GDELT-Streamer system as a research-grade, interactive geopolitical monitoring platform. The system merges live event streams (GDELT), forecast intelligence (ACLED CAST), and curated geopolitical interactions into a single map-first interface with auditable, deterministic data handling. It emphasizes provenance, reproducibility, and measurable data governance through explicit retention policies, archival, and reports.

## Goals
- Provide an interactive world map that supports exploration of countries, admin1 regions, and districts.
- Display live events and interactions with clickable, source-backed context.
- Integrate forecast data (ACLED CAST) and visualize it on both the panel and the map.
- Maintain research-grade data hygiene with retention, archiving, and audit reports.
- Keep processing pipelines modular, replayable, and testable.

## System Overview
The system is split into three major planes:

1. Frontend (Leaflet + Vanilla JS)
2. Backend API (FastAPI)
3. Ingestion and processing pipelines (Python)

High-level data flow:

- Live GDELT export and mentions are pulled every 15 minutes by the backend Firehose service.
- Live data is stored as GeoJSON and served via the API or directly from disk for map rendering.
- ACLED CAST is fetched on-demand, cached, and visualized as both a panel report and a choropleth map.
- GDELT GKG daily counts are aggregated into DuckDB and CSV summaries.
- Interactions are curated from manifests and processed via legacy collectors and processors.

## Repository Structure (Relevant)
- Frontend application: `src/`
- Backend API: `server/`
- Ingestion pipelines: `ingestion_engine/`
- Data storage: `data/`
- Research and design: `RnD/`

## Core Runtime Components

### Frontend Application
Entry point: `src/main.js`

Managers:
- `DataManager`: Loads static datasets and polls the backend for live updates.
- `MapManager`: Owns Leaflet map lifecycle, GeoJSON rendering, and choropleth logic.
- `UIManager`: Builds the side panel, tabs, and CAST forecast visualization.
- `InteractionManager`: Loads and renders interactions from `data/interactions/manifest.json`.
- `SufferingLayer`: Live event layer with smart decluttering and category filtering.

Key runtime interactions:
- The map is initialized with Leaflet tiles and base GeoJSON layers.
- Clicking a region opens the side panel and triggers CAST data fetch.
- Switching to the CAST tab sends visibility and data events for map coloring.

### Backend API
File: `server/main.py`

Endpoints:
- `GET /api/live`: Serves the latest GeoJSON event collection.
- `GET /api/cast`: Fetches ACLED CAST data for a country and optional admin1, with caching.
- `GET /api/health`: Health status of the firehose.

The backend runs a Firehose service that continuously pulls GDELT data and persists it to disk in `data/live/gdelt_latest.json`.

### Ingestion Pipelines
The ingestion layer is split into:

1. Live stream ingestion (backend Firehose)
2. GKG batch processing (gkg_pipeline)
3. Interaction data pipeline (legacy processors)

## Data Sources and Update Cadence

### GDELT (Global Database of Events, Language, and Tone)
- Export and mentions files (GDELT v2) are pulled every 15 minutes.
- Counts (GKG daily) are pulled daily, aggregated by country and admin1.

### ACLED CAST
- CAST forecasts are fetched on demand using ACLED OAuth.
- Cached locally with year-specific keys for repeatability.

### Reference Datasets
- Country metadata, capitals, currency, volatility, and sources are loaded from `data/` JSON files at startup.
- Interactions are curated under `data/interactions/` with a versioned manifest.

## Data Products and Formats

### Live Event GeoJSON
Stored at: `data/live/gdelt_latest.json`

Schema (feature properties):
- `category` (CONFLICT, VIOLENCE, PROTEST, CRIME, DISASTER, ACCIDENT, etc.)
- `name` (human-readable label)
- `date` (GDELT date field)
- `countryname` (GDELT ActionGeo_FullName)
- `importance` (derived from GDELT NumArticles)
- `sourceurl` and `sources` (list of URLs)

### ACLED CAST Payload
Fetched via `GET /api/cast` and rendered by `UIManager.renderPredictions()`.
Key fields used:
- `year`, `month`
- `total_forecast`, `battles_forecast`, `erv_forecast`, `vac_forecast`
- `admin1` (for regional hotspots)
- `timestamp` (if present, used for display)

Derived view model:
- `latestCast.rows`: list of admin1 totals used by the choropleth
- `latestCast.label`: e.g. "February 2026"

### GKG Aggregates
Processed via `ingestion_engine/gkg_pipeline/process_data.py`.
Output files:
- `data/processed/gdelt_metrics_YYYYMMDD.csv`
- `data/processed/gdelt_admin1_metrics_YYYYMMDD.csv`

DuckDB tables:
- `gdelt_metrics` (date, country, metric_type, count, num_sources)
- `gdelt_admin1_metrics` (date, country, admin1, metric_type, count, num_sources)

### Interactions Manifest
`data/interactions/manifest.json` includes:
- `categories` metadata
- `interactions` list per category

Each interaction entry contains:
- `participants` and topology (mesh, star, chain)
- `type`, `status`, `date`
- `file` reference for detailed records

## Data Handling and Clustering Strategy

### GDELT Live Events
- Events are filtered for relevance using taxonomy mapping.
- Events without sources or with zero sources are dropped.
- Only categories mapped in `server/app/core/taxonomy.py` are retained.

### Smart Decluttering (SufferingLayer)
- A 5x5 degree grid is used to estimate density.
- When density is high, stricter thresholds are applied:
  - Density > 20: importance >= 3
  - Density > 5: importance >= 2
  - Otherwise: all events shown
- The top 30 most recent or important events are rendered as pulsing markers.

### CAST Choropleth
- Choropleth is only applied when the CAST tab is visible and the map is at admin1 level.
- Admin1 names are normalized and matched using:
  - Diacritics removal
  - Stop-word stripping
  - Token normalization and expansion
  - Token-based and fuzzy matching with conservative thresholds
- Color scale is generated from 0 to max value, with white as the default base.
- Capitals remain red and are explicitly excluded from CAST coloring.

### GKG Aggregation
- Daily counts are aggregated by:
  - `date + country + metric_type`
  - `date + country + admin1 + metric_type`
- This enables both country-level and admin1-level analysis.

## Retention and Archival Policy
Retention and archival are implemented in `ingestion_engine/gkg_pipeline/retention_cleanup.py` with measurable audit output.

Defaults (configurable in `ingestion_engine/gkg_pipeline/config.yaml`):
- raw 15-minute GKG files: 7 days
- raw gkgcounts files: 90 days
- processed outputs: 365 days

### Archival Strategy
- Archive path layout:
  - `data/archive/gkg/{file_kind}/YYYY/MM/DD/{basename}.parquet`
- Parquet compression: ZSTD
- No deletion occurs without a successful archive write (fail-safe design).

### DuckDB Retention
- Rows older than `processed_days` are deleted from:
  - `gdelt_metrics`
  - `gdelt_admin1_metrics`
- Optional VACUUM ensures on-disk compaction.

### Audit Reports
Retention runs generate JSON reports in `logs/retention/` that include:
- Bytes and file counts before and after
- Archived, deleted, skipped counts
- DB row deletions
- Runtime and configuration snapshot

## Operational Runbook

### Frontend
- Development server: `npm run dev`
- Production build: `npm run build`

### Backend
- Run API: `uvicorn server.main:app --reload --reload-dir server`

### GKG Pipeline
- Update pipeline:
  - `python ingestion_engine/gkg_pipeline/update_pipeline.py`
- Run retention dry-run:
  - `python ingestion_engine/gkg_pipeline/retention_cleanup.py`
- Apply retention:
  - `python ingestion_engine/gkg_pipeline/retention_cleanup.py --apply --vacuum`

## Data Quality and Validation
- GDELT events can be noisy; strict filtering reduces false positives.
- ACLED CAST data uses on-demand fetches; caching avoids repeated requests.
- Admin1 name matching uses multi-stage normalization and conservative fuzzy matching.
- A debug overlay prints CAST admin1 values for visual verification.

## Security and Governance
- ACLED OAuth credentials are currently stored in `server/app/services/acled.py`.
- For production use, move credentials to environment variables or a secrets manager.
- CORS is open for local development; tighten in production.

## Limitations
- GDELT category mapping is heuristic and may omit edge cases.
- Admin1 names may still mismatch in rare cases with ambiguous naming.
- CAST data depends on external API availability.
- Live data uses a polling model; true streaming is not implemented.

## Future Work
- Automated validation of admin1 matching across all countries.
- Time series dashboards from DuckDB aggregates.
- Additional data providers and ensemble forecasting.
- Improved provenance tracking for data lineage at row level.
- Expand hotspot analytics with longitudinal baselines and anomaly scoring.

## References Within the Repository
- System architecture: `RnD/ARCHITECTURE.md`
- Interactions schema: `RnD/INTERACTIONS.md`
- GKG pipeline goal: `RnD/Features/GDELT-GKG-1.md`
- Retention plan: `RnD/Features/gdelt-data-retention-me.md`
- Event tracker methodology: `RnD/EVENT_TRACKER.md`
