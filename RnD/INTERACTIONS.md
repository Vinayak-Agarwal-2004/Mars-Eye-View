# Interactions System

## Overview

A modular, source-agnostic system for managing international interactions between nations. Designed to support automated ingestion from LLMs, news feeds, and other sources.

---

## Categories

| Category | Icon | Color | Description |
|----------|------|-------|-------------|
| **Disputes** | ⚠️ | Red | Territorial, political, trade conflicts |
| **Meetings** | 🤝 | Blue | Summits, bilateral/multilateral talks |
| **Agreements** | 📜 | Green | Treaties, trade deals, peace accords |
| **Sports** | 🏆 | Amber | Olympics, World Cup, championships |
| **Trade** | 💰 | Purple | Sanctions, tariffs, investments |
| **Military** | 🛡️ | Slate | Exercises, alliances, deployments |
| **Humanitarian** | 🏥 | Pink | Disaster relief, refugee aid |
| **Cultural** | 🎭 | Cyan | Exchanges, festivals, education |
| **Other** | 🌐 | Gray | Miscellaneous interactions |

---

## File Structure

```
data/interactions/
├── manifest.json           # Master index (v2.0)
├── disputes/               # 19 territorial disputes
├── meetings/               # Summits & talks
├── agreements/             # Treaties & deals
├── sports/                 # Sporting events
├── trade/                  # Economic relations
├── military/               # Defense activities
├── humanitarian/           # Aid & relief
├── cultural/               # Exchanges & education
└── other/                  # Miscellaneous
```

---

## Category Subtypes

### Disputes
`territorial`, `sovereignty`, `maritime`, `political`, `trade`, `diplomatic`, `resource`, `ethnic`, `war`, `border_crisis`

### Meetings
`summit`, `bilateral`, `multilateral`, `state_visit`, `politburo`, `g7`, `g20`, `un`, `asean`, `nato`, `eu`, `brics`

### Agreements
`treaty`, `trade_deal`, `defense_pact`, `ceasefire`, `peace_accord`, `mou`, `fta`, `extradition`

### Sports
`olympics`, `world_cup`, `commonwealth`, `asian_games`, `friendly`, `championship`, `cricket`, `formula1`

### Trade
`sanction`, `tariff`, `embargo`, `investment`, `aid`, `loan`, `currency`

### Military
`exercise`, `deployment`, `alliance`, `arms_deal`, `incident`, `patrol`

### Humanitarian
`disaster_relief`, `refugee`, `medical`, `food_aid`, `evacuation`

### Cultural
`exchange`, `festival`, `education`, `tourism`, `heritage`

---

## Manifest Schema (v2.0)

```json
{
  "version": "2.0",
  "categories": {
    "<category_id>": {
      "name": "Display Name",
      "description": "Category description",
      "subtypes": ["type1", "type2"],
      "icon": "emoji",
      "color": "#hex",
      "arc_style": "dashed|solid|dotted"
    }
  },
  "interactions": {
    "<category_id>": [...]
  }
}
```

---

## Interaction Entry Schema

```json
{
  "id": "unique_id",
  "name": "Display Name",
  "type": "subtype",
  "status": "Current status",
  "participants": ["ISO3", "ISO3"],
  "topology": "mesh|star|chain",
  "hub": "ISO3",
  "short_description": "Brief description",
  "file": "category/unique_id.json",
  "date": "2025-01-15",
  "location": {"iso": "USA"} | {"lat": 0, "lon": 0},
  "visualization_type": "geodesic|dot",
  "arc_style": "dashed|solid|dotted",
  "toast_message": "Optional toast text",
  "toast_type": "info|success|warning|error",
  "llm_analysis": "Refined analysis text",
  "llm_analysis_cached": true,
  "source": "llm|news_scraper|gdelt_*"
}
```

### Canonical event schema (ingestion)

Events sent to the Interactions Receiver (e.g. `POST /api/interactions/ingest` or via `raw_llm_events.json` / `raw_news_events.json`) must normalize to:

- **Required**: `name`, `participants` (list; may be empty for `visualization_type: "dot"`).
- **Optional**: `type`, `category`, `subtype`, `description`, `status`, `date`, `topology`, `hub`, `source_url` / `source_urls`, `visualization_type` (default `geodesic`), `arc_style` (default `solid`), `location` (for dots: `{lat, lon}` or `{iso}`), `toast_message`, `toast_type`, `source` (`llm` | `news_scraper` | `gdelt_conflict` | `gdelt_diplomatic` | `gdelt`).

---

## Topology Guidelines

The visualization system supports three network topologies to represent interactions clearly. Use the `topology` field to select the appropriate mode.

### 1. Mesh Topology (`mesh`)
**Default Behavior**: Connects every participant to every other participant pairwise (`N * (N-1) / 2` arcs).
**Use Case**: Decentralized interactions or mutual conflicts where no single entity is the focus.
- **Trade Wars**: e.g., US-China Tariff War (if bidirectional).
- **Disputes**: e.g., South China Sea (overlapping claims among many claimants).
- **Alliances**: e.g., NATO (without highlighting a specific leader/host).

### 2. Star Topology (`star`)
**Behavior**: Connects all "Spoke" participants to a single central "Hub" (`N-1` arcs).
**Requirement**: Must provide `"hub": "ISO3"`.
**Use Case**: Centralized events, hosted summits, or unidirectional flows.
- **Summits/Games**: Hub is the **Host** (e.g., G20 in ZAF, Olympics in FRA).
- **Humanitarian Aid**: Hub is the **Recipient** (e.g., Turkey Earthquake).
- **Sanctions**: Hub is the **Target** (e.g., Sanctions on Russia - RUS is the hub).

### 3. Chain Topology (`chain`)
**Behavior**: Connects participants in a specific sequence: A → B → C (`N-1` arcs).
**Use Case**: Sequential routes or tiered relationships.
- **Trade Routes**: e.g., Belt and Road Initiative segments.
- **Supply Chains**: e.g., Component manufacturing flow.

---

## User Interface & Visuals

### 1. Arc Rendering
- **Bezier Curves**: Interactions are rendered as Quadratic Bezier curves to simulate "flight paths".
- **Arc Height**: The curvature height scales with distance (longer arcs = higher curves).
- **IDL Crossing**: The system automatically detects arcs crossing the International Date Line and wraps them correctly to avoid visual artifacts.

### 2. Interaction Flow
The system follows a specific 3-step interaction model:
1.  **Hover (Discovery)**:
    -   Effect: **Group Highlighting**. Hovering over *any* arc in an interaction highlights *all* related arcs (e.g., hovering one G20 line lights up the entire summit network).
    -   No tooltips are shown to reduce clutter.
2.  **Click (Summary)**:
    -   Action: clicking an arc opens a **Popup**.
    -   Content: Basic info (Name, Type, Hub/Status) and a "More Details" button.
3.  **Details (Deep Dive)**:
    -   Action: clicking "More Details" in the popup.
    -   Effect: Opens the **Side Panel** with comprehensive data (Participants list, full description, history).


## Adding New Interactions

### 1. Add to manifest.json

```json
{
  "id": "g20_summit_2025",
  "name": "G20 Summit 2025",
  "type": "g20",
  "status": "Scheduled",
  "participants": ["USA", "CHN", "IND", "..."],
  "short_description": "Annual G20 summit in South Africa",
  "file": "meetings/g20_summit_2025.json",
  "date": "2025-11-15"
}
```

### 2. Create Individual File (Optional)
For detailed data: `data/interactions/{category}/{id}.json`

---

## Adding New Categories

1. Add to `categories` in manifest.json:
```json
"space": {
  "name": "Space",
  "description": "Space exploration cooperation",
  "subtypes": ["iss", "moon", "mars", "satellite"],
  "icon": "🚀",
  "color": "#1e3a5f",
  "arc_style": "solid"
}
```

2. Create folder: `data/interactions/space/`

3. Add array to `interactions`: `"space": []`

4. Update UI toggle (Automatic via `app.js` manifest loader)

---

## Ingestion Pipeline (Implemented)

```
┌─────────────────────┐     ┌─────────────────────┐
│   DATA COLLECTORS   │     │   DATA PROCESSORS   │
│                     │     │                     │
│  ┌───────────────┐  │     │  ┌───────────────┐  │
│  │ RSS Collector │──┼────▶│  │ Geocoder      │  │
│  └───────────────┘  │     │  └───────┬───────┘  │
│                     │     │          │          │
│  ┌───────────────┐  │     │  ┌───────▼───────┐  │
│  │ LLM Collector │──┼────▶│  │ Deduplicator  │  │
│  └───────────────┘  │     │  └───────┬───────┘  │
│                     │     │          │          │
│                     │     │  ┌───────▼───────┐  │
│                     │     │  │ Manifest      │  │
│                     │     │  │ Writer        │  │
│                     │     │  └───────────────┘  │
└─────────────────────┘     └─────────────────────┘
```

**Separation of concerns:**
- `scripts/collectors/` - Data acquisition (RSS, LLM)
- `scripts/processors/` - Data processing (NER, geocoding, dedup)

---

## Related Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Core design
- [TODO_FUTURE.md](./TODO_FUTURE.md) - Roadmap
