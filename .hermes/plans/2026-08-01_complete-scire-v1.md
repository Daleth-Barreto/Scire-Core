# Scire — Completion Plan (finish the project)

> **For Hermes:** implement task-by-task with TDD; every task ends with a runnable demo or green tests. Follow `AGENTS.md` and `ROADMAP.md`; keep them updated as you go (self-improvement protocol).

**Goal:** Take Scire from its current state (all roadmap phases except one Phase-8 item; healthy but unversioned codebase) to a finished, versioned, hardened v1.0 with the remaining Phase-8 feature done and the highest-impact known limitations resolved.

**Architecture:** Python 3.12 + FastAPI backend, PostgreSQL 16 + pgvector storage, React + TypeScript (Vite + React Flow) frontend, Typer CLI. LLM via multi-provider abstraction (dev machine: OmniRoute local gateway at `localhost:20128/v1`).

**Tech stack:** Python 3.12, FastAPI, SQLAlchemy, pgvector, Typer, httpx, pytest, ruff, mypy, uv; React 19, Vite, TypeScript, @xyflow/react; `cryptography` (new, for encrypt-at-rest).

---

## Verified current state (2026-08-01)

- 65 tests pass (`uv run pytest`), `ruff check .` clean, `mypy backend cli` clean (42 files).
- Postgres 16 + pgvector running natively on `localhost:5432` (db `scire`, role `scire/scire`); `scire_test` DB used by tests.
- ROADMAP: Phases 0–7 `[x]`; Phase 8 all `[x]` **except** *"API-key settings UI that writes keys + encrypt-at-rest with a user passphrase"*.
- Frontend Settings tab (`frontend/src/SettingsView.tsx`) is read-only; backend only exposes `GET /api/config` (masked) — no write endpoint.
- Feedback loop working: 3 bugs fixed 2026-07-31, each with regression test + AGENTS.md updates.
- **No git repository** in `C:\scire` (AGENTS.md said greenfield; still true).
- `.gitignore` exists (130 B). `docker-compose.yml` exists but Docker is NOT installed (Postgres runs natively — keep it that way).
- `.env` present with OmniRoute keys (never commit it).

### Environment note for Hermes sessions

When running project commands from the Hermes terminal, the shell injects `PYTHONPATH=C:\Users\aland\AppData\Local\hermes\hermes-agent;...\venv\Lib\site-packages`, which breaks imports (pydantic from the wrong venv, `cli` package shadowing). **Always prefix project commands with `PYTHONPATH=`** (e.g. `PYTHONPATH= uv run pytest`). This is a shell quirk, not a project bug — the user's normal terminal does not need it.

---

## Phase A — Version control (do first, ~30 min)

Protect the work before anything else.

### Task A1: Init git repo with a clean baseline

**Objective:** Put the entire project under version control with a single well-formed initial commit.

**Files:**
- Create: `.gitignore` entries check (must ignore `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `frontend/node_modules/`, `frontend/dist/`, `.scire/` if created in Phase B)
- Modify: `.gitignore` (add any missing entries)

**Steps:**
1. `cd /c/scire && PYTHONPATH= uv run pytest -q` → expect 65 passed (baseline recorded).
2. `git init` (default branch `main`).
3. Ensure `.gitignore` covers: `.env`, `.venv/`, `*.pyc`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `node_modules/`, `frontend/dist/`, `.scire/`.
4. `git add -A && git status` → confirm `.env` and `.venv/` are NOT staged.
5. `git commit -m "chore: initial commit — phases 0-8 (except settings UI), 65 tests green"`.
6. Verify: `git log --oneline` shows 1 commit; `git ls-files | grep -c ""` reasonable (< 1000, no venv files).

### Task A2: Define commit convention

**Objective:** Lock in the convention the rest of the plan uses.

**Files:**
- Modify: `AGENTS.md` (add one line under Rules: commit message convention `type(scope): description`, e.g. `feat(config): encrypted key store`)

**Steps:**
1. Add the rule to `AGENTS.md`.
2. Commit: `git add AGENTS.md && git commit -m "docs: add commit convention to AGENTS.md"`.

---

## Phase B — Finish Phase 8: encrypted settings UI (the one unchecked roadmap item)

New dependency: `cryptography`. Design: keys are encrypted at rest with a passphrase-derived key (PBKDF2HMAC + Fernet/AES-GCM) into `~/.scire/keys.enc`; the passphrase is never stored; decrypted keys live in process memory only (per session). `.env` remains supported as today — encryption is an additional, optional store the UI can manage.

### Task B1: Add `cryptography` dependency

**Objective:** Declare the encryption library.

**Files:**
- Modify: `pyproject.toml`, `uv.lock`

**Steps:**
1. `cd /c/scire && PYTHONPATH= uv add cryptography` → expect lockfile update, install OK.
2. `PYTHONPATH= uv run pytest -q` → 65 passed (no regression).

### Task B2: Write failing tests for the secret store

**Objective:** Define expected behavior of `backend/core/secrets.py` before writing it.

**Files:**
- Create: `tests/test_secrets.py`

**Step 1: Write the test** (copy-pasteable):

```python
import pytest
from backend.core.secrets import (
    decrypt_keys,
    derive_key,
    encrypt_keys,
    SecretStoreError,
)

def test_roundtrip(tmp_path):
    path = tmp_path / "keys.enc"
    keys = {"OPENAI_API_KEY": "sk-123", "GITHUB_TOKEN": "ghp_abc"}
    encrypt_keys("passphrase", keys, path)
    assert decrypt_keys("passphrase", path) == keys

def test_wrong_passphrase_raises(tmp_path):
    path = tmp_path / "keys.enc"
    encrypt_keys("right", {"OPENAI_API_KEY": "sk-123"}, path)
    with pytest.raises(SecretStoreError):
        decrypt_keys("wrong", path)

def test_tampered_file_raises(tmp_path):
    path = tmp_path / "keys.enc"
    encrypt_keys("pass", {"OPENAI_API_KEY": "sk-123"}, path)
    path.write_bytes(path.read_bytes()[:-4] + b"\x00\x00\x00\x00")
    with pytest.raises(SecretStoreError):
        decrypt_keys("pass", path)

def test_missing_file_raises(tmp_path):
    with pytest.raises(SecretStoreError):
        decrypt_keys("pass", tmp_path / "nope.enc")

def test_derive_key_deterministic():
    k1 = derive_key("passphrase", b"salt")
    k2 = derive_key("passphrase", b"salt")
    k3 = derive_key("passphrase", b"other")
    assert k1 == k2 and k1 != k3

def test_file_not_plaintext(tmp_path):
    path = tmp_path / "keys.enc"
    encrypt_keys("pass", {"OPENAI_API_KEY": "sk-123"}, path)
    assert b"sk-123" not in path.read_bytes()
```

**Step 2: Run to verify failure**

Run: `cd /c/scire && PYTHONPATH= uv run pytest tests/test_secrets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.core.secrets'`.

### Task B3: Implement the secret store

**Objective:** Pass B2. Passphrase-derived key + authenticated encryption (PBKDF2HMAC + Fernet), versioned JSON envelope `{version, salt, ciphertext}`.

**Files:**
- Create: `backend/core/secrets.py` (module: `derive_key(passphrase, salt) -> bytes`, `encrypt_keys(passphrase, keys: dict[str, str], path) -> None`, `decrypt_keys(passphrase, path) -> dict[str, str]`, `SecretStoreError`; keys stored under a per-user dir — use `Path.home() / ".scire"` for the default location)
- Modify: `backend/core/__init__.py` (nothing needed unless exports)

**Steps:**
1. Implement using `cryptography.hazmat.primitives.kdf.pbkdf2hmac.PBKDF2HMAC` + `cryptography.fernet.Fernet`.
2. `PYTHONPATH= uv run pytest tests/test_secrets.py -v` → 6 passed.
3. Full suite: `PYTHONPATH= uv run pytest -q` → 71 passed.
4. Commit: `git add tests/test_secrets.py backend/core/secrets.py pyproject.toml uv.lock && git commit -m "feat(config): encrypted key store (passphrase + Fernet)"`.

### Task B4: Settings-write + unlock API endpoints

**Objective:** Backend endpoints so the UI can save keys (encrypted) and unlock them for the session. Keys are never returned; responses stay masked.

**Files:**
- Modify: `backend/api/schemas.py` (add `ConfigKeysIn {passphrase: str, keys: dict[str, str]}`, `ConfigUnlockIn {passphrase: str}`, extend `ConfigOut` with `encrypted: bool`)
- Modify: `backend/api/main.py` (add `POST /api/config/keys`, `POST /api/config/unlock`, `POST /api/config/lock`; extend `GET /api/config` to report `encrypted`)
- Modify: `backend/core/config.py` (session key overlay: after unlock, provider factory sees decrypted keys in memory)
- Modify: `backend/core/envfile.py` (no change expected — read-only path stays)

**Step 1: Write failing tests first** — add to `tests/test_api.py`:
- `test_config_keys_write_creates_encrypted_file` — POST keys+passphrase → 200, file exists in tmp home, content has no plaintext key.
- `test_config_unlock_roundtrip` — POST `/api/config/keys`, then POST `/api/config/unlock` → 200 and `GET /api/config` shows key as set (masked), then `POST /api/config/lock` → unset again.
- `test_config_keys_never_returned` — all responses contain masked values (`sk-123` substring never appears).
- Use `tmp_path` + monkeypatched home dir (see `tests/conftest.py` patterns; conftest already isolates DB).

**Step 2: Run to verify failure** — `PYTHONPATH= uv run pytest tests/test_api.py -v` → new tests FAIL (endpoint missing).

**Step 3: Implement** — endpoints in `backend/api/main.py`; session store (module-level dict or `get_settings()` overlay) in `backend/core/config.py`.

**Step 4: Verify** — `PYTHONPATH= uv run pytest tests/test_api.py -v` → all pass; full suite green; `PYTHONPATH= uv run ruff check .` clean; `PYTHONPATH= uv run mypy backend cli` clean.

**Step 5: Commit** — `git add -A && git commit -m "feat(api): config write/unlock endpoints with encrypted key store"`.

### Task B5: Frontend Settings tab — write keys + unlock UI

**Objective:** Settings tab edits keys: passphrase field, per-key inputs (password type), Save (encrypts to disk), Unlock/Lock buttons, status feedback. Mirrors the read-only info already shown.

**Files:**
- Modify: `frontend/src/api.ts` (add `saveConfigKeys(passphrase, keys)`, `unlockConfig(passphrase)`, `lockConfig()`; extend `ConfigInfo` with `encrypted: boolean`)
- Modify: `frontend/src/SettingsView.tsx` (form + buttons + status messages; keep masked display)
- Modify: `frontend/src/App.css` if needed for form styles

**Steps:**
1. Update `api.ts` types/functions (types mirror backend schemas).
2. Rewrite `SettingsView.tsx`: table of key inputs prefilled with masked values, passphrase input, Save / Unlock / Lock buttons, inline error/success text (no new dependencies).
3. Verify: `cd frontend && npm run lint` (oxlint) clean; `npm run build` (tsc -b && vite build) succeeds.
4. Manual check with backend running: `PYTHONPATH= uv run uvicorn backend.api.main:app --reload` + `cd frontend && npm run dev` → open `http://localhost:5173`, Settings tab: save a key, reload page (still encrypted on disk), unlock, see it set. (Per AGENTS.md: all network/LLM mocked in tests; UI manual check is the demo.)
5. Commit: `git add frontend/src && git commit -m "feat(ui): settings tab writes and unlocks encrypted keys"`.

### Task B6: Docs + roadmap update

**Objective:** Roadmap checkbox closed; AGENTS.md reflects the new capability.

**Files:**
- Modify: `ROADMAP.md` (check the Phase 8 settings item; note the `~/.scire/keys.enc` design)
- Modify: `AGENTS.md` (Known limitations: mark "no persistent auth" as still true; add note that keys CAN be encrypted at rest via passphrase; update Required test suite with `test_secrets.py`)
- Modify: `README.md` (short "Encrypted keys" section: passphrase semantics + warning that losing the passphrase loses the keys)

**Steps:**
1. Apply edits.
2. `git add -A && git commit -m "docs: close phase 8 settings item, document encrypted keys"`.

---

## Phase C — Known limitations, prioritized (pick per week; each is optional but recommended)

Order = impact ÷ effort. Do C1–C2 before C3–C6.

### Task C1: Cross-source dedup for papers

**Objective:** Same paper from arXiv vs web should be ONE node, not two. (Limitation line already exists in AGENTS.md: "cross-source dedup still pending".)

**Files:**
- Modify: `backend/graph/store.py` (add `find_paper_by_title(title)` using normalized-title lookup: lowercase, strip punctuation/whitespace; and `merge_nodes(keep_id, drop_id)`)
- Modify: `backend/search/persist.py` (before inserting a candidate paper, check normalized-title collision across sources → merge instead of insert)
- Create: `tests/test_dedup.py`
- Modify: `backend/graph/json_export.py` + `backend/graph/ascii.py` if merge affects them (should not)

**Tests (TDD):**
- `test_same_title_different_source_merges` — insert paper via arXiv source, then same title via web source → 1 node, both `external_id`/`source` values recorded.
- `test_different_titles_do_not_merge`.
- `test_merge_preserves_edges` — edges pointing at dropped node re-point to keeper.

**Verify:** new tests green, full suite green, ruff + mypy clean. Commit: `feat(graph): cross-source paper dedup by normalized title`.

**Stretch (same task, separate commit):** `scire graph dedupe --dry-run` CLI command that lists existing duplicate pairs (one-time cleanup of pre-fix duplicates).

### Task C2: Disk cache for search adapters

**Objective:** Repeated searches shouldn't re-hit rate-limited APIs. Cache adapter responses (arXiv, Semantic Scholar, DuckDuckGo) on disk with TTL.

**Files:**
- Create: `backend/core/cache.py` (small `DiskCache` class: `get(key) -> Any | None`, `set(key, value, ttl)`, key = sha256 of (adapter, query, params); JSON on disk under `~/.cache/scire/`; thread-safe enough via atomic rename)
- Modify: `backend/search/arxiv.py`, `backend/search/semantic_scholar.py`, `backend/search/duckduckgo.py` (check cache before HTTP, store after)
- Create: `tests/test_cache.py`; extend `tests/test_search_adapters.py` (second identical call → mocked transport NOT hit again)

**Tests (TDD):**
- `test_cache_hit_skips_network` — mock httpx transport, call adapter twice with same query → transport called once.
- `test_cache_ttl_expiry` — ttl=0 → second call hits network.
- `test_cache_persists_across_instances` — new DiskCache instance on same path returns cached value.

**Verify:** green + full suite + ruff/mypy. Commit: `feat(search): disk cache for web/academic adapters`.

### Task C3: Graph schema versioning + lightweight migrations

**Objective:** Escape "no schema versioning or migration path" — with the least machinery (YAGNI: no Alembic yet).

**Files:**
- Create: `backend/graph/migrations/__init__.py`, `backend/graph/migrations/0001_initial.py` (creates tables/vector columns via SQLAlchemy `metadata.create_all`), `backend/graph/migrate.py` (`schema_version` table; `migrate(engine)` applies pending numbered steps in order, records applied versions)
- Modify: `backend/graph/db.py` (call `migrate` on init; keep behavior identical)
- Modify: `cli/commands/graph.py` (add `scire graph migrate`)
- Create: `tests/test_migrations.py`

**Tests (TDD):**
- `test_migrate_from_empty_db` — fresh `scire_test` schema-less DB → `migrate` creates tables + version row.
- `test_migrate_idempotent` — run twice → no error, same version.
- `test_new_migration_applied_in_order` — fake 0002 migration → applied after 0001.

**Verify:** green, full suite, ruff/mypy. Commit: `feat(graph): lightweight schema migrations`.

### Task C4: Streaming support in LLMProvider (optional but high UX value)

**Objective:** `scire chat` and the UI chat stream tokens instead of blocking. Tool/function calling stays deferred (no concrete use case yet — YAGNI).

**Files:**
- Modify: `backend/core/providers.py` (add `stream(messages) -> Iterator[str]` to `LLMProvider` ABC + OpenAI-compatible implementations; OmniRoute: must send `stream:false` fallback — see Known limitations, keep the non-stream path intact)
- Modify: `backend/shell.py` + `cli/commands/shell.py` (chat paths use `stream` when provider supports it)
- Modify: `backend/api/main.py` (chat endpoint stays non-streaming for now — SSE is a separate feature; note it)
- Extend: `tests/test_providers.py` (mocked streaming response parsed token-by-token)

**Verify:** green, full suite, ruff/mypy; manual: `PYTHONPATH= uv run scire chat "hello"` streams. Commit: `feat(providers): token streaming for chat`.

### Task C5: Ollama offline provider (needs Ollama installed — confirm with user first)

**Objective:** Local models via Ollama's OpenAI-compatible endpoint (`http://localhost:11434/v1`), no API key.

**Files:**
- Modify: `backend/core/providers.py` (add `OllamaProvider`; factory keyed by `LLM_PROVIDER=ollama`)
- Modify: `.env.example` (document `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`)
- Extend: `tests/test_providers.py` (mocked Ollama chat/embed)

**Verify:** green; optional real smoke if Ollama installed. Commit: `feat(providers): ollama offline provider`.

**Open question for user:** install Ollama on the dev machine? If no, this task is code-only (tested with mocks).

### Task C6: Rate-limit backoff + retry

**Objective:** 429s (OmniRoute, Semantic Scholar, GitHub) retry with exponential backoff + jitter instead of degrading instantly (degradation stays as the final fallback).

**Files:**
- Create: `backend/core/retry.py` (`retry_on_rate_limit(fn, attempts=3)`, honors `Retry-After` header when present, sleeps with jitter)
- Modify: `backend/core/providers.py` (chat/embed wrap 429 retry), `backend/search/semantic_scholar.py`, `backend/repos/github.py`
- Create: `tests/test_retry.py` (mock transport: 429 twice → success; assert backoff sleeps patched; `Retry-After` honored)

**Verify:** green, full suite, ruff/mypy. Commit: `feat(core): retry with backoff on rate limits`.

### Task C7: PDF tables/formulas — STRETCH, do not commit to

**Objective:** Evaluate pdfplumber as an optional parser for tables (keep pypdf default). Mark as a spike (`spike` skill) with a timebox; if tables matter for the user's actual documents, promote to a task; else close the limitation as "accepted for v1".

**Files (spike only):**
- Create: `notes/` or throwaway script parsing 2–3 real PDFs; no production changes.

**Verify:** report findings; either open a follow-up task or update AGENTS.md limitation to "accepted: plain text only in v1".

---

## Phase D — Hardening & docs

### Task D1: API exposure guardrails (optional, decide with user)

**Objective:** AGENTS.md says the API has no auth and must not be exposed. Decide: (a) keep localhost-only and document (zero work), or (b) add optional `SCIRE_API_TOKEN` bearer check behind an env flag.

**Files (if b):** `backend/api/main.py` (tiny FastAPI dependency checking `Authorization: Bearer <token>` when `SCIRE_API_TOKEN` is set), `.env.example`, `tests/test_api.py` (token required when set, open when unset).

**Verify:** green. Commit: `feat(api): optional bearer token guard`.

### Task D2: Frontend + README polish

**Objective:** `npm run build` green; README gets a "Web UI" section with the tabs, the encryption flow, and a screenshot if the user wants one.

**Files:** `frontend/` (as needed), `README.md`.

**Verify:** `cd frontend && npm run build`; README links render. Commit: `docs: web UI section + polish`.

### Task D3: Real-API smoke test

**Objective:** End-to-end proof with the real OmniRoute gateway (the one test that is skipped in CI).

**Steps:**
1. `cd /c/scire && PYTHONPATH= SCIRE_CI=1 uv run pytest tests/test_api.py::test_chat_smoke -v` (or run `PYTHONPATH= uv run scire chat "hola, quién eres?"` manually — the original unicode-crash repro, now expected to print an emoji reply).
2. `PYTHONPATH= uv run scire search "knowledge graphs"` → real results; persist one.
3. `PYTHONPATH= uv run scire repo add <small_repo>` (e.g. `psf/requests`) → subgraph + `repo ask` with citation (the 429/timeout repro paths, now fixed).
4. Record results in the final demo notes.

---

## Phase E — Release

### Task E1: Full verification pass

**Objective:** Everything green from a clean slate.

**Steps:**
1. `cd /c/scire && PYTHONPATH= uv sync && PYTHONPATH= uv run pytest -q` → all pass.
2. `PYTHONPATH= uv run ruff check . && PYTHONPATH= uv run mypy backend cli`.
3. `cd frontend && npm run build`.
4. Update `AGENTS.md` Required test suite checkboxes + Known limitations (remove resolved items, mark `[x]`).

### Task E2: Tag release

**Steps:**
1. Update `pyproject.toml` version → `0.9.0` after Phase B, `1.0.0` after Phase C (whatever lands).
2. `git add -A && git commit -m "chore: v1.0.0"` and `git tag v1.0.0`.
3. Suggest a remote (GitHub private repo) — `git remote add origin <url> && git push -u origin main` only if the user provides it.

### Task E3: Demo script (CLI + UI)

**Objective:** 5-minute repeatable demo proving the whole pipeline.

**Content (write to `docs/demo.md`):**
1. `scire chat` (streaming, emoji-safe output) — Phase C4.
2. `scire search "retrieval augmented generation"` → persist a paper → `graph show` ASCII tree — Phase 2/4.
3. `scire repo add psf/requests` + `scire repo ask` with citation — Phase 5.
4. `scire ingest pdf <file>` — Phase 3.
5. Web UI: Graph tab (nodes/gaps), Search tab (persist), Repo tab (ask), Settings tab (encrypted key save/unlock) — Phase 8 + B.

---

## Risks, tradeoffs, open questions

| # | Item | Decision / note |
|---|---|---|
| 1 | No git remote | Ask user: GitHub private repo? (needs account/gh auth) |
| 2 | Passphrase UX | Lost passphrase = unrecoverable keys (by design). Warn in UI. Re-save with same passphrase re-encrypts. |
| 3 | `cryptography` dependency | New dep; pure-Python fallback not considered — `cryptography` wheels are standard. |
| 4 | Ollama install | Ask user before C5; code is mock-tested regardless. |
| 5 | LLM caching | Deliberately NOT in C2 (cost/latency tradeoff, non-determinism). Revisit only if user asks. |
| 6 | Alembic vs lightweight migrations | Lightweight chosen (YAGNI); Alembic later if the schema grows. |
| 7 | Tool/function calling | Deferred (no concrete use case). |
| 8 | Auth | Default: localhost-only, documented. Optional token behind env flag (D1). |
| 9 | Docker vs native Postgres | Native wins on this machine (no Docker). docker-compose stays for other machines. |
| 10 | Hermes shell PYTHONPATH | `PYTHONPATH=` prefix needed for uv commands from Hermes terminal (see env note above). |
| 11 | Phase C scope | C1–C2 recommended before C3–C6; C7 is a spike. Confirm priorities with the user. |

## Definition of done (v1.0)

- [ ] Git repo with history, no secrets committed.
- [ ] Phase 8 checkbox closed: settings UI writes keys, encrypt-at-rest + unlock works end-to-end (UI + API + CLI-compatible).
- [ ] C1–C2 merged (dedup + cache); C3–C6 as agreed; C7 spiked or closed.
- [ ] 65+ tests green, ruff + mypy clean, frontend builds.
- [ ] Real-API smoke test passed on the dev machine.
- [ ] AGENTS.md limitations/tests reflect reality; ROADMAP fully checked; README updated.
- [ ] v1.0.0 tagged; `docs/demo.md` exists.
