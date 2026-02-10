## Local secrets (current)

- Secrets are loaded from `.env.local` (gitignored by default).
- The backend reads secrets from environment variables first; `.env.local` is only for local development.

### Required env vars (for full features)

- `OPENROUTER_API_KEY`: OpenRouter API key used by the LLM pipeline (or use `GROQ_API_KEY`).
- `OPENROUTER_MODEL` (optional): defaults to `openai/gpt-4o-mini`.
- `ACLED_EMAIL`, `ACLED_KEY`: ACLED API credentials for CAST forecasts (optional; omit to skip CAST).

### Optional controls

- `GDELT_LLM_MAX_PER_RUN`: cap number of GDELT events sent to LLM per run (0 = no cap).
- `GDELT_LLM_DELAY_SEC`: delay between LLM calls (rate limiting).

## Framework for future security (deployment-ready)

When deploying, do **not** ship `.env.local`. Use one of:

- **Container/orchestrator secrets**: Kubernetes Secrets, Docker Swarm secrets, ECS task secrets.
- **Cloud secrets manager**: AWS Secrets Manager, GCP Secret Manager, Azure Key Vault.
- **CI/CD injected env vars**: inject `OPENROUTER_API_KEY` at runtime.

Recommended future hardening:

- Restrict CORS origins from `*` to your deployed domain(s).
- Add auth for write endpoints like `POST /api/interactions/process-gdelt` and `POST /api/interactions/ingest`.
- Add request rate limiting and audit logging for LLM-triggering endpoints.

