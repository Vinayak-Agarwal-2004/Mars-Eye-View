# Architecture & Design Decisions

## Project Overview
This project is an **Interactive World Map** that allows users to explore administrative divisions (Countries → States → Districts) and view comprehensive data including geopolitical interactions, demographics, and leadership.

## Core Architecture

### 1. Technology Stack
- **Map Engine**: `Leaflet.js` (v1.9.4).
  - *Reasoning*: Lightweight, open-source, extensible.
- **Data Format**: `GeoJSON`.
  - *Reasoning*: Standard format. Used with a "Drill-Down" strategy (Country → State → District) to minimize load.
- **Styling**: Pure CSS + Google Fonts (Inter).
  - *Reasoning*: No heavyweight frameworks (Tailwind/Bootstrap).
- **Logic**: Vanilla JavaScript (ES6+).
  - *Reasoning*: Encapsulated in `app.js` IIFE.

### 2. Data Strategy
- **Hierarchical Loading**: `countries.geojson` (L0) → `adm1/{ISO}.geojson` (L1) → `adm2/{ISO}.geojson` (L2).
- **Lazy Loading**: High-res data is only fetched on zoom to prevent browser crash.

### 3. Interactions Visualization
- **Scope**: Replaces legacy "Disputes" system. Supports War, Trade, Meetings, Sports.
- **Layer Groups**: Segregated by category (Disputes, Meetings, etc.).
- **Custom Pane**: `interactionPane` (z-index 450) floats above map tiles but below labels.

#### "Ghost Line" Technique
We render two polylines for every interaction:
1. **Visual Line**: Thin (2px), styled (dashed/solid).
2. **Hit Line**: Thick (15px), invisible (`opacity: 0`).
*Benefit*: Pixel-perfect visuals with massive click targets for better UX.

#### Geodesic Arcs
- **Implementation**: Custom `createGeodesicArc` function using spherical interpolation.
- **Reasoning**: Straight lines on Mercator look distorted. Curves look natural.

### 4. User Interaction
- **Drill-Down**: Click Country → Zoom → Load States.
- **Breadcrumbs**: Persistent navigation bar.
- **Side Panel**: Context-aware content (Flag, Neighbors, Interaction Details).
- **Sidepanel Tabs**: Tabbed interface ("Info", "Dummy", etc.) for organizing panel content.

---

## Design Decisions Log (Requested)

### System Structure
- **Decision**: Renamed "Disputes" to "Interactions".
- **Reasoning**: "Disputes" was too narrow. The system needed to support Meetings, Trade Agreements, and Sports. "Interactions" is the generic superset.
- **Implication**: Directory structure moved to `data/interactions/`. Manifest v2.0 introduces `categories` object.

### Data Ingestion Pipeline
- **Decision**: Decoupled Collection from Processing.
- **Reasoning**: Collectors fetch raw strings (prone to network failure); Processors clean data (logic-heavy). Separation allows replaying processing on raw data without re-fetching.
- **Implication**: Raw data saved to `raw_rss_events.json` before processing.

### Visualization Strategy
- **Decision**: Dual-Line Rendering ("Ghost Lines").
- **Reasoning**: 2px visual lines are hard to click.
- **Solution**: Render two overlapping lines per interaction: a thin visible one and a 15px invisible interactive one.

### UI Styling
- **Decision**: Professional Flat Design (No Emojis, No Gradients).
- **Reasoning**: User feedback indicated previous design was "too flashy". Serious geopolitical tools require neutral, high-contrast displays.
- **Implication**: Replaced emoji icons with color-coded CSS dots. Removed gradients.

### Nested Filtering
- **Decision**: Client-Side Subtype Filtering.
- **Reasoning**: Users need to filter "Wars" specifically within "Disputes".
- **Implementation**: `updateInteractionVisibility` dynamically rebuilds layer groups based on selected subtypes.

### Sidepanel Tabs
- **Decision**: Restored Tabbed Interface for Sidepanel.
- **Reasoning**: To support multiple views (Info, Wikipedia, Dummy template) without cluttering a single long scroll view.
- **Naming**: Officially designated as "Sidepanel Tabs".
- **Implementation**: HTML Buttons with `data-tab` attributes + `switchTab()` function in `app.js`.

### UI/UX Standards (Research Grade)
- **Decision**: Adopted "Research Grade" aesthetic for Interaction Panel.
- **Specs**:
    - **Border Radius**: `0px` (Squared edges).
    - **Shadows**: Hard shadows (`2px 2px 0px`), no blur.
    - **Typography**: Compact, high contrast (`#333` on white), `11px` base size.
    - **Spacing**: Minimal padding (`4px` - `6px`) to maximize data density.

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Core design decisions (this file) |
| [INTERACTIONS.md](./INTERACTIONS.md) | Interactions system manual |
| [TODO_FUTURE.md](./TODO_FUTURE.md) | Roadmap & future features |

## Future Considerations
- **LLM Ingestion**: Fully automated news-to-map pipeline.
- **Global Search**: Jump to specific districts/events.
- **Vector Tiles**: MVT support for scaling beyond GeoJSON limits.
