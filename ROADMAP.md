# Scire — Development Roadmap

## Decisions (locked in)

| Decision | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Frontend (later) | React + TypeScript |
| First interface | CLI |
| Database | PostgreSQL + pgvector |
| LLM | Multi-provider, user-supplied API keys, OpenRouter-compatible; dev machine uses OmniRoute (local gateway, `localhost:20128/v1`) |
| Repo state | `C:\scire` — greenfield, start from scratch |

## Architecture (target)

```
scire/
├── cli/                  # CLI entrypoint (Typer/Click)
├── backend/
│   ├── api/              # FastAPI app (added in web phase)
│   ├── core/             # Config, LLM provider abstraction
│   ├── graph/            # Knowledge graph models + storage (pgvector)
│   ├── ingest/           # PDF / document ingestion
│   ├── search/           # Web + academic search adapters
│   ├── repos/            # GitHub repo analysis (DeepWiki-style)
│   └── memory/           # User thoughts/actions persistence
├── frontend/             # React app (later phase)
└── tests/
```

Key interfaces:

- `LLMProvider` — abstract; implementations: `OpenAIProvider`, `AnthropicProvider`, `OpenRouterProvider`. All use the OpenAI-compatible chat schema where possible. API keys come from a user-level config (`.env` / settings store), never hardcoded.
- `GraphStore` — wraps Postgres + pgvector. Nodes: papers, authors, concepts, hypotheses, repos, notes. Edges: cites, authored_by, supports, refutes, gap_in, extends, mentions.
- `DocumentParser` — PDF → plain text → chunks → embeddings (via LLM provider or local embedding model) → stored in pgvector.

## Phases

### Phase 0 — Project scaffold
- [ ] `uv init` / `pyproject.toml`, virtualenv, deps: `fastapi`, `sqlalchemy`, `pgvector`, `typer`, `httpx`, `pydantic`, `pydantic-settings`.
- [ ] Dev environment: Postgres container (`docker-compose.yml`) with `pgvector` extension enabled.
- [ ] `.env.example` with placeholder keys (OPENROUTER_API_KEY, OPENAI_API_KEY, etc.).
- [ ] Config module that loads provider + key at runtime.

### Phase 1 — LLM provider abstraction (foundation)
- [x] `LLMProvider` ABC: `chat(messages) -> str`, `embed(text) -> list[float]`.
- [x] Implement `OpenRouterProvider` first (covers GPT, Claude, and hundreds of models behind one key).
- [x] Implement `OpenAIProvider` and `AnthropicProvider` as thin adapters.
- [x] Provider factory keyed by config; CLI `scire chat "prompt"` (real LLM call, the smoke test) + `scire whoami` for key status.
- [x] Tests: mock HTTP responses, no real API calls.

### Phase 2 — Knowledge graph (storage)
- [x] SQLAlchemy models for nodes/edges with a `vector` column (pgvector) for embeddings.
- [x] Graph CRUD: upsert node, upsert edge, query neighbors (1-hop/2-hop).
- [x] Semantic search: `graph search "query"` → nearest vectors.
- [x] CLI commands: `node add`, `node list`, `edge add`, `graph init`, `graph search`.

### Phase 3 — Document ingestion
- [x] PDF parser (pypdf) → text.
- [x] Chunking strategy (paragraph/section aware).
- [x] Extraction pipeline: embed chunks, extract entities (authors, key terms, claims) via LLM.
- [x] Store extracted entities + claims as graph nodes.
- [x] CLI: `scire ingest pdf paper.pdf` (plus `--extract-only` to inspect text/chunks).

### Phase 4 — Search & discovery
- [x] Web search adapter — DuckDuckGo HTML scraping, no API key needed (`backend/search/duckduckgo.py`; shown as `(web)` results; Tavily/Exa/SERPer swap-in later if user wants).
- [x] Academic adapters: arXiv API (free, no key), Semantic Scholar API.
- [x] Results become candidate nodes; user confirms to persist them.
- [x] CLI: `scire search "topic"`, `scire paper fetch arxiv:2301.00000`.

### Phase 5 — Repository analysis (DeepWiki-style)
- [x] GitHub adapter (fetch repo tree + file contents via REST, user GitHub token).
- [x] Repo summary pipeline: map structure → LLM-generated explainer.
- [x] Repo ingested as subgraph (repo/files/chunks → nodes; contains/has_chunk → edges).
- [x] Q&A against repo: chunk index + semantic search, LLM answers with file:line citations.
- [x] CLI: `scire repo add owner/name`, `scire repo ask owner/name "how does X work?"`.

### Phase 6 — Memory & user actions
- [x] Persist user thoughts/notes as special nodes tied to context (`scire note add --context`, `scire note list`).
- [x] Log user actions (searches, reads, ingests) as edges to create a personal context graph.
- [x] Gap detection: LLM scans graph for unlinked/suspect regions, surfaces candidate hypotheses (`scire graph gaps`).

### Phase 7 — CLI polish
- [x] Interactive mode (`scire shell` REPL; commands `/note`, `/graph`, `/search`, `/gaps`, `/export`, `/import`, `/help`, `/quit`; bare lines ask the LLM).
- [x] `/note` to save a thought in context; `/graph` to visualize as ASCII tree (`backend/graph/ascii.py`: `render_tree`, `find_hub`).
- [x] Export/import graph to JSON (`backend/graph/json_export.py`; CLI `graph export/import/show`).

### Phase 8 — Web UI (React)
- [x] FastAPI API surface (`backend/api/main.py`): graph dump/detail/search/gaps, web search + persist, repo add/ask, notes, chat, config (keys masked). Endpoints documented in the OpenAPI schema at `/docs`.
- [x] React + TypeScript frontend (Vite) with React Flow (`frontend/`); tabs Graph / Search / Repo / Notes / Settings; Vite proxies `/api` to the backend.
- [x] Live map: click node → details + neighbors in a sidebar; drag/zoom/fitView; node colors by type.
- [x] Overlay gaps/hypotheses on the live map: "Detect gaps" button + hypotheses list in the sidebar; hypothesis nodes get a dashed pink border and `gap_in` edges a dashed red stroke.
- [x] API-key settings UI that writes keys (`scire config set` remains the CLI way), plus encrypt-at-rest with a user passphrase.
- [x] PDF ingest behind the API (`POST /api/ingest/pdf` + "Ingest" tab in the UI); pipeline dedupes authors/concepts/claims by title on re-ingest.
- [x] `paper fetch` behind the API (`POST /api/papers/fetch`, persists by default, UI input in the Search tab).

## Validation strategy
- pytest for unit/integration (mocked network), a `tests/` dir grows with each phase.
- Every phase ends with a runnable CLI demo — no phase depends on a later one.
- Real-API smoke tests guarded by env var `SCIRE_CI=1` (skipped in CI).

## First milestone (do this week)
Phase 0 + Phase 1 + a minimal Phase 2 (`graph search` working with Postgres) — enough to prove the plumbing end-to-end.
