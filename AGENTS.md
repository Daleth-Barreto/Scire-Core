# AGENTS.md — Scire Project Instructions

This file is the operating manual for AI agents (and humans) working on Scire. Read it before touching any code.

## Project

Scire is an AI research copilot that builds a living knowledge graph (papers, authors, hypotheses, repos, notes), searches the web and academic sources, analyzes GitHub repos (DeepWiki-style), and ingests PDFs. Backend: Python 3.12 + FastAPI. Storage: PostgreSQL + pgvector. LLM: multi-provider, user-supplied API keys; active provider on the dev machine is OmniRoute (local gateway), with OpenRouter/OpenAI/Anthropic as alternatives. First interface: CLI.

## Canonical documents

- `IDEA.md` — product vision.
- `ROADMAP.md` — phases, decisions, architecture. Follow it; do not skip phases.

## Commands

- Install deps: `uv sync`
- Run tests: `uv run pytest`
- Run a single test: `uv run pytest tests/test_x.py::test_y`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Typecheck: `uv run mypy backend cli`
- Run CLI: `uv run scire ...`
- Run dev server: `uv run uvicorn backend.api.main:app --reload`
- Run web UI (dev): `cd frontend && npm run dev` (proxies `/api` to `localhost:8000`; run uvicorn first)
- Build web UI: `cd frontend && npm run build`

## Architecture map

```
cli/       CLI entrypoint (Typer)
backend/
  api/     FastAPI (web phase)
  core/    Config + LLM provider abstraction
  graph/   Graph models + pgvector storage
  ingest/  PDF ingestion
  search/  Web + academic adapters
  repos/   GitHub repo analysis
  memory/  User thoughts/actions
  shell.py Interactive REPL (scire shell)
frontend/  React + TypeScript UI (Vite, React Flow)
tests/     pytest suite
feedback/  Retroalimentación del usuario (see below)
```

## Rules

- No comments in code unless asked. No emojis in code/docs unless asked.
- Do not commit secrets. API keys live only in user config / `.env`, never hardcoded.
- Never print full API keys in CLI output. `scire config show` and `whoami` only report masked values or set/unset status.
- All network/LLM calls MUST go behind an abstraction so tests can mock them.
- Tests MUST be hermetic: they pass with an empty `.env.example` and no real network. Embedding paths use the `fake_embedder` fixture (patches `get_embedder` at every import site) — never rely on real keys being present.
- All httpx clients MUST set explicit timeouts (LLM providers 120s, API adapters 30s); never rely on httpx's 5s default.
- Optional LLM/embedding steps (summaries, embeddings, extractions) MUST catch `httpx.HTTPError` and degrade, never abort the command on a rate limit or network error.
- The CLI entrypoint forces UTF-8 on stdout/stderr (`errors="replace"`) — on Windows cp1252 consoles any Unicode output would otherwise crash with `UnicodeEncodeError`.
- English for code, docs, and commit messages. You may converse with the user in Spanish.
- Follow `ROADMAP.md` order. Each phase must end with a runnable CLI demo.

### Commit signatures

- **Routine / minor changes** that need no user approval (docs tweaks, tests, bug fixes, implementing an already-approved plan) are committed with the agent's identity:
  - `hermes <hermes@scire.local>` when Hermes Agent made the change.
  - `opencode <opencode@scire.local>` when an OpenCode agent made the change.
- **Architecture-level changes**, changes that affect locked decisions, or anything the user explicitly confirmed/approved are committed as the developer:
  - `desarrollador <desarrollador@scire.local>`
- Mechanism — set author AND committer per commit (one of):
  ```bash
  GIT_AUTHOR_NAME=hermes GIT_AUTHOR_EMAIL=hermes@scire.local \
  GIT_COMMITTER_NAME=hermes GIT_COMMITTER_EMAIL=hermes@scire.local \
  git commit -m "..."
  # or
  git -c user.name=hermes -c user.email=hermes@scire.local commit -m "..."
  ```
- The initial baseline commit predates this rule and keeps the developer's global identity.
- If in doubt about the category, ask the user — a signature you can defend beats a forced push.

## Known limitations

Tracked here on purpose. Update this list when a limitation is discovered or resolved.

- [ ] Typer pinned to `0.26.8` — `0.27.0` regresses subcommands (a single-command app collapses to a root command); a `@app.callback()` is required to force group mode.
- [ ] OmniRoute (local gateway, `localhost:20128/v1`) streams SSE by default — the provider must send `stream:false`. Current active provider on the dev machine.
- [ ] Docker not installed on the dev machine — Postgres runs natively instead: PostgreSQL 16 (EDB installer, silent, `postgres/scirepass`) + pgvector 0.8.3 (precompiled binaries from `andreiramani/pgvector_pgsql_windows`, requires elevated copy into `C:\Program Files\PostgreSQL\16\{lib,share\extension}`). DB `scire`, role `scire/scire`, extension created as superuser then used by `scire`. `ALTER EXTENSION ... OWNER TO` fails with a parse error — do not rely on it.
- [ ] pgvector extension must be created per-database as superuser. Tests run against a separate `scire_test` DB (`CREATE DATABASE scire_test OWNER scire` + `CREATE EXTENSION vector` as postgres); if unavailable, graph tests skip via `tests/conftest.py`.
- [ ] `LLMProvider` — only chat + embed defined; no streaming, no tool/function calling yet.
- [ ] No persistent auth or multi-user model; single local user only. The FastAPI app binds localhost and has no auth — do not expose it publicly.
- [ ] PDF parsing is plain text only (no tables/formulas yet).
- [ ] No rate limiting / quota handling for external APIs.
- [ ] Encrypted key store (`~/.scire/keys.enc`, override with `SCIRE_KEYS_PATH`): keys are unlocked per-process into memory; a server/CLI restart re-locks them, and losing the passphrase makes stored keys unrecoverable (by design).
- [ ] OmniRoute (local gateway) can return HTTP 429 on `/v1/embeddings` or chat under load — optional LLM/embedding steps degrade to un-embedded nodes instead of aborting.
- [x] Node deduplication: papers dedupe by (source, external_id), authors by title, repo re-indexing is idempotent (repo/files/chunks). Limitation resolved 2026-07-31; cross-source dedup (same paper in arXiv vs web) and cleanup of pre-fix duplicates still pending.
- [ ] Semantic Scholar API without a key is rate-limited (HTTP 429) — `scire search` degrades gracefully and returns arXiv + OpenAlex + DuckDuckGo results. OpenAlex (added 2026-08-02) is the keyless fallback for paper metadata.
- [ ] Europe PMC (added 2026-08-02) — search/fetch work keyless via `EXT_ID:`/`PMCID:` search; the `fullTextXML` endpoint has been returning 404 for all IDs (observed 2026-08-02, even for the docs' own example), so `scire paper fulltext epmc:<id>` reports "fulltext not available" until the service recovers.
- [ ] DuckDuckGo web adapter scrapes `duckduckgo.com/html/` HTML — no API key, but the HTML layout can change and the endpoint may 302/429 or serve a CAPTCHA; it is best-effort, not a hard SLA.
- [ ] GitHub API without a token is rate-limited (60 req/hr) — `scire repo add` works for small repos; set `GITHUB_TOKEN` in `.env` to index large ones.
- [ ] No caching layer for repeated search/LLM calls.
- [ ] Graph has no schema versioning or migration path beyond raw SQLAlchemy.
- [ ] OpenRouter compatible, but embedding models not available on OpenRouter — embeddings use OpenAI or the OmniRoute `/v1/embeddings` endpoint instead.
- [ ] No offline/local model support yet (Ollama planned).
- [ ] Prompt injection surface: `deepresearch`/`audit`/ingest feed external text (paper titles, abstracts, PDF text) into LLM prompts without sanitization. The verifier stage mitigates unsupported claims, but a hostile document could still steer the researcher/writer. Accepted risk for a local single-user tool; revisit if multi-user/web.
- [ ] `tempfile.mktemp` historically used in `cli/commands/search.py` fulltext path — replaced with `mkstemp` (TOCTOU-safe) in the 2026-08-02 QA pass.

## Required test suite

These must pass before any merge. Extend the list as the project grows.

- [x] `test_providers.py` — LLM provider factory returns correct adapter; all providers mocked, no real network.
- [x] `test_openrouter.py` — request body matches OpenAI-compatible schema; key passed via header, not logged.
- [x] `test_graph_crud.py` — node upsert, edge upsert, neighbor queries.
- [x] `test_graph_search.py` — vector search returns nearest neighbors; empty graph returns empty result.
- [x] `test_graph_rank.py` — PaperRank scores papers by relevance + citations (edges and OpenAlex `cited_by_count`) + method evidence (repo/claim/hypothesis neighbors) + provenance weight.
- [x] `test_ingest.py` — PDF fixture → text → chunks; entities extracted with mocked LLM; re-ingest dedupes authors/concepts/claims by title.
- [x] `test_search_adapters.py` — arXiv + OpenAlex + Semantic Scholar + Europe PMC + DuckDuckGo (web) adapters parse mocked responses into candidate nodes; Europe PMC fulltext XML parsing.
- [x] `test_repos.py` — mocked GitHub API: repo tree → subgraph; Q&A returns cited answer.
- [x] `test_audit.py` — paper claims vs repo chunks: LLM verdicts (supported/refuted/not-evidenced) with `path:line` evidence; missing paper/claims/repo errors.
- [x] `test_deepresearch.py` — multi-agent pipeline: researcher synthesizes real sources → writer briefs with `[n]` citations → verifier flags unsupported claims; degrades on HTTP errors and unparseable output.
- [x] `test_init.py` — `scire init` wizard: `.env` from `.env.example` (no overwrite), role/DB/pgvector creation via admin URL (psycopg, detects existing), table readiness.
- [x] `test_memory.py` — user note persisted as node tied to context; actions logged as edges.
- [x] `test_config.py` — API keys never logged/serialized into graph.
- [x] `test_secrets.py` — encrypted key store: roundtrip, wrong passphrase, tampered/missing file, no plaintext on disk, parent dir creation.
- [x] `test_api.py` — FastAPI: graph dump/detail/search, web search adapter merge, paper fetch, PDF upload ingest, notes roundtrip, masked config, config keys write/unlock/lock (keys never returned), chat action logging (TestClient against `scire_test`).
- [x] `test_cli.py` — `scire whoami` reports provider + key status without a real key.
- [x] `test_shell.py` — ASCII render (`render_tree`/`find_hub`), JSON export/import roundtrip, `scire shell` REPL commands (all network/LLM mocked).
- [ ] Smoke test (skipped when `SCIRE_CI=1`): real LLM call via `scire chat`.

## Feedback loop

All user feedback and observed failures are stored as dated files in `feedback/`:

```
feedback/YYYY-MM-DD_short-slug.md
```

Format of each file:

```markdown
## Type
bug | limitation | feature-request | usability | docs

## Summary
One or two lines describing the issue.

## Repro / context
Steps or the conversation excerpt that triggered it.

## Impact
How much it blocks work (high/med/low) and for whom.

## Suggested fix (optional)
```

## Self-improvement protocol

Each feedback file drives a closed loop. Whenever a feedback file is created, update the project files so the system improves permanently:

1. **Resolve**: if it is a bug, fix it in code and add/adjust the test that would have caught it.
2. **Consolidate**:
   - If a new failure mode appears → add it to **Known limitations**.
   - If it was a real bug → add a regression test to **Required test suite** and check it.
   - If it changed how we work → add a line under **Rules**.
3. **Mark done**: append a `## Resolution` section to the feedback file with the date, what changed, and which files/tests it touched. Check the boxes above accordingly.
4. **Verify**: run `uv run pytest` and `uv run ruff check .` before finishing.

This is what makes the project self-improving: nothing gets fixed twice the same way, and every lesson is recorded where the next agent will read it.

## Before you finish any task

- Update `AGENTS.md` limitations/tests if your work changed what the project can/cannot do.
- If the user gave feedback (verbal or written), record it in `feedback/` and run the protocol above.
- Run the full test suite, lint, and typecheck; report results.
