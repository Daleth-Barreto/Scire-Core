# Scire — AI Research Copilot

An AI research copilot that builds a living knowledge graph (papers, authors, hypotheses, repos, notes), searches web and academic sources, analyzes GitHub repos (DeepWiki-style), and ingests PDFs.

- `IDEA.md` — product vision.
- `ROADMAP.md` — phases, decisions, architecture.
- `AGENTS.md` — operating manual for agents and humans working on the codebase.

## Stack

- Backend: Python 3.12 + FastAPI, PostgreSQL 16 + pgvector (SQLAlchemy).
- LLM: multi-provider (OpenRouter/OpenAI/Anthropic/OmniRoute), user-supplied API keys.
- CLI: Typer (`scire ...`).
- Frontend: React + TypeScript (Vite, React Flow).

## Quickstart

```bash
uv sync                      # install deps
cp .env.example .env         # fill in your keys
uv run uvicorn backend.api.main:app --reload   # backend on :8000
cd frontend && npm install && npm run dev      # UI on :5173 (proxies /api)
```

CLI:

```bash
uv run scire chat "what is a knowledge graph?"
uv run scire search "retrieval augmented generation"
uv run scire paper fetch oa:W4389984066
uv run scire paper fetch epmc:41547989
uv run scire paper fulltext epmc:PMC12921246
uv run scire rank "retrieval augmented generation"   # PaperRank with evidence
uv run scire repo add psf/requests && uv run scire repo ask psf/requests "how does X work?"
uv run scire audit "Attention Paper" psf/requests    # paper claims vs repo code
uv run scire deepresearch "retrieval augmented generation"   # multi-agent cited brief
uv run scire ingest pdf paper.pdf
uv run scire shell            # interactive REPL
```

## Tests

```bash
uv run pytest        # 75+ tests, network/LLM mocked
uv run ruff check . && uv run mypy backend cli
```

Graph tests need a `scire_test` Postgres database (skipped if unavailable).

## Encrypted keys (web UI)

The Settings tab can store API keys encrypted at rest instead of plain `.env`:

- Enter a passphrase and the keys you want to persist, then **Save keys (encrypt)**.
- Keys are encrypted (PBKDF2 + Fernet) into `~/.scire/keys.enc` — never as plaintext on disk.
- **Unlock** decrypts them into memory for the current process; **Lock** clears them. A server/CLI restart re-locks automatically.
- Losing the passphrase makes the stored keys unrecoverable — there is no backdoor.
- The CLI path is unchanged: `scire config set <key> <value>` still writes `.env`.
- Set `SCIRE_KEYS_PATH` to relocate the encrypted store (handy for tests).

## Scope

Prototype/research tool, single local user. The API binds localhost and has no auth — do not expose it publicly.
