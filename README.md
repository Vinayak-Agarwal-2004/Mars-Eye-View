# GDELT-Streamer

GDELT event streaming, conflict/diplomacy analytics, news ingestion, and an interactive map frontend. Backend ingests from GDELT API, RSS, and optional LLM analysis; serves live GeoJSON and ACLED CAST forecasts.

## Stack

- **Backend**: Python (FastAPI), [ingestion_engine](ingestion_engine/README.md) (DuckDB, pandas, feedparser, newspaper3k)
- **Frontend**: Vite, Leaflet, vanilla JS ([src/](src/))
- **Server**: [server/](server/README.md) — firehose, `/api/live`, `/api/cast`, interactions, Wikipedia

## Quick start

1. **Clone and install**
   ```bash
   python -m venv venv && source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   npm install
   ```

2. **Environment**
   - Copy `.env.example` to `.env` or `.env.local` and set API keys (see [SECURITY.md](SECURITY.md)).
   - Optional: `OPENROUTER_API_KEY`, `GROQ_API_KEY` for LLM pipeline; `ACLED_EMAIL`, `ACLED_KEY` for CAST forecasts.

3. **Run**
   - Backend: `cd server && uvicorn main:app --reload`
   - Frontend: `npm run dev`
   - Open the app URL (e.g. http://localhost:5173).

## Repo layout

| Path | Description |
|------|-------------|
| [ingestion_engine/](ingestion_engine/README.md) | GDELT firehose, conflict/diplomacy monitors, news scraper, LLM analysis, manifest writer |
| [server/](server/README.md) | FastAPI app, firehose service, ACLED, interactions API |
| [src/](src/README.md) | Map UI, data managers, layers |
| [data/](data/README.md) | GeoJSON, live JSON, DuckDB, interactions |
| [tests/](tests/README.md) | Unit, integration, e2e |
| [RnD/](RnD/README.md) | Research notes and feature docs |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## License

ISC. See [LICENSE](LICENSE).
