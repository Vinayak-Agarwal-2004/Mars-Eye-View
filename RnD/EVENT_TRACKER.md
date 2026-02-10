# Event Tracker & Hotspot Analyzer (GDELT Only)

Date: 2026-02-03
Version: 1.0

## Purpose
This module detects **emerging events** and **hotspots** using only GDELT export data. It answers:

- Where are events clustering spatially?
- Which event categories or codes are surging?
- Which actors or involved parties are appearing repeatedly in a short window?

The system is **ACLED-free** and is designed for research-grade repeatability.

## Core Principles
- **Provenance-first**: Every hotspot includes the top source URLs that produced the signal.
- **Deterministic**: Same data and parameters yield the same output.
- **Conservative matching**: Clusters are derived from explicit fields (event code, location, actors).
- **Explainable scoring**: Each hotspot has a transparent trend calculation.

## Data Inputs
Source: `server/app/services/firehose.py`

The live firehose now produces enriched GDELT features with:
- `eventid` (GDELT GlobalEventID)
- `eventcode` (GDELT EventCode)
- `actor1`, `actor2` (participant names)
- `actiongeo`, `actionadm1` (location strings)
- `ingested_at` (UTC timestamp)

A rolling window of events is stored in:
- `data/live/gdelt_window.json` (30-day lookup window)

The latest automatic hotspot output is stored in:
- `data/live/hotspots_latest.json`

## Methodology

### 1. Windowed Event Collection
- Current window: **7 days** (168 hours)
- Previous window: **30 days** (720 hours), used as the lookup baseline

These two windows form the baseline for trend detection.

### 2. Clustering Dimensions

#### A. Location Hotspots
Events are clustered into geographic grid cells (default `grid_km = 120`).

- Grid cell size is derived from `grid_km / 111` degrees.
- Each cell accumulates:
  - event count
  - weighted count (by `importance`)
  - category and event-code distribution
  - top source URLs

This yields **spatial hotspots** that explain *where* activity is emerging.

#### B. Event Hotspots
Events are grouped by:

```
(eventcode + category + actiongeo)
```

This yields **semantic hotspots** (same type of event, same place).

#### C. Actor Hotspots
Actors are normalized and tracked across the same window.

- Normalization removes punctuation, lowercases, and collapses whitespace.
- Actor hotspots explain *who* is repeatedly involved.

### 3. Scoring
Each cluster is scored by:

```
trend = (current_count - previous_count) / max(1, previous_count)
score = weighted_count * (1 + trend)
```

Interpretation:
- High volume + strong trend rise = top hotspots
- If previous_count is zero, trend inflates and is capped by `max(1, previous)`

### 4. Output
Endpoint:

```
GET /api/hotspots
```

Parameters:
- `window_hours`: current analysis window (default 168)
- `previous_hours`: baseline window (default 720)
- `grid_km`: spatial granularity
- `top`: number of hotspots per cluster

Response fields:
- `hotspots.location` (grid clusters)
- `hotspots.event` (event-code clusters)
- `hotspots.actor` (actor clusters)
- Each includes score, trend, counts, top categories, top sources

## Automatic Operation
- Hotspots are computed automatically on every GDELT refresh cycle.
- Output is written to `data/live/hotspots_latest.json` for downstream dashboards or analysts.

## Research-Grade Considerations
- **Bias control**: event counts are weighted by GDELT `importance`.
- **Noise resistance**: actor and event clustering require shared identifiers.
- **Auditability**: each hotspot includes top source URLs for validation.
- **Repeatability**: retention window ensures consistent re-analysis.

## Recommended Practices
- Use the default **7-day vs 30-day** comparison for stable weekly trend detection.
- Use smaller `grid_km` (60–80) for country-level analysis, larger for global.
- Track consecutive runs in `logs/` if you need longitudinal tracking.

## Example

```
GET /api/hotspots?window_hours=168&previous_hours=720&grid_km=100&top=10
```

This produces global hotspot clusters for the last 7 days compared to the prior 30 days.

## Files Implemented
- `server/app/services/hotspot.py`
- `server/app/services/firehose.py` (rolling window + metadata)
- `server/main.py` (new endpoint)
