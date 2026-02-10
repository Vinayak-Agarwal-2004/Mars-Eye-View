# Future Tasks & Roadmap

## High Priority

### Dispute System Enhancements
> See [DISPUTES.md](./DISPUTES.md) for current implementation

- [ ] **LLM-Powered Dispute Ingestion**
  - Automated pipeline: News/LLM → NER → Geocoding → Dispute Creation
  - Use existing data (`country_info.json`, `capitals.json`) for location resolution
  - LLM only for disambiguation when multiple matches exist
  
- [ ] **Dispute Deduplication System**
  - Same-dispute detection via name/alias matching, claimant overlap, geo-proximity
  - Future: LLM-assisted semantic matching
  
- [ ] **Manual Dispute Entry UI**
  - Admin form for adding disputes manually
  - Review queue for low-confidence automated entries

---

## UI / UX

- [ ] **Metals & Commodities Display**
  - Data feed includes Gold, Silver, Crypto rates
  - *Decision needed*: Where to display? (Panel, ticker, or world view)

- [ ] **Currency Historical Data**
  - When clicked on currency, show past 1-year data in graph

- [ ] **Tabbed Panel System** ✅ (Implemented)
  - Info | Data | More tabs for organized content

---

## Map Features

- [ ] **Custom Polygon Coloring (ADM1/ADM2)**
  - Color specific states/districts with custom colors on demand
  - Architecture ready: `renderLayer()` uses centralized `style` function
  
  **Implementation Options:**
  
  1. **Data-driven** - Create `data/region_colors.json`
  2. **Callback-based** - Pass `colorFn` to `renderLayer`
  3. **Overlay layer** - Separate `L.geoJSON` for highlights

- [ ] **Global Search**
  - Search bar to jump to specific countries/states/districts
  - Fuzzy matching with autocomplete

- [ ] **Vector Tiles**
  - If dataset grows >100MB, switch from GeoJSON to MVT

---

## Data Pipeline

- [ ] **ADM3 Level Support**
  - Sub-district/tehsil level for major countries
  - Requires significant data download (~500MB+)

- [ ] **News Geocoding Pipeline**
  - NER extraction (spaCy) → Gazetteer lookup → LLM disambiguation
  - Reference: Perplexity research on multi-stage geocoding

---

## Documentation

- [x] [ARCHITECTURE.md](./ARCHITECTURE.md) - Core design decisions
- [x] [INTERACTIONS.md](./INTERACTIONS.md) - Interactions system documentation
- [x] [TODO_FUTURE.md](./TODO_FUTURE.md) - This roadmap
