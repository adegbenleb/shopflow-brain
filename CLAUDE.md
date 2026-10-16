# ShopFlow Company Brain

## Purpose
A personal learning and portfolio project: an AI assistant that answers questions about
customers, buying behaviour, marketing, finance and products for a fictional online store.
It reads only the gold tables and documents produced by the sister repo `shopflow-platform`.

## Planned structure
- `knowledge/`: loaders for Qdrant (documents) and Neo4j (graph), plus the semantic layer
- `agents/`: LangGraph agents (and an Agno version for comparison)
- `api/`: FastAPI REST, GraphQL and an MCP server
- `app/`: Streamlit chat UI
- `evals/`: evaluation sets and scripts
- `security/`: data classification, access rules, prompt injection tests
- `tests/`: pytest tests

## Commands
- Install: `uv sync`
- Lint and format: `uv run ruff check . --fix && uv run ruff format .`
- Test: `uv run pytest -q`

## Services it uses (started from shopflow-platform)
- Postgres gold tables: localhost:15432
- Qdrant: http://localhost:16333
- Neo4j: bolt://localhost:17687
- Ollama (local LLM): http://localhost:11434

## Rules
- Personal project only. Never add code, data, credentials or context from any employer.
- LLM calls use local models through Ollama by default. No company API keys, ever.
- Never commit `.env` or any secret. Use `.env.example` for placeholders.
- Customer PII is masked by default, and finance data is restricted, even in this demo.
- Every new feature comes with at least one test, and CI must stay green.
- Python 3.12, managed with uv. Format and lint with ruff.
- Record important design choices and trade-offs in `docs/decisions.md`.
- Explain what you change and why, so the owner learns from each step.
