#!/usr/bin/env bash
# Scire one-command install (Linux/macOS/git-bash).
# Usage: bash scripts/install.sh  (optionally: ADMIN_URL=postgresql+psycopg://postgres:pass@localhost:5432/postgres)
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found — installing via pipx..."
    python3 -m pip install --user uv
fi

echo "==> installing dependencies (uv sync)"
uv sync

echo "==> running scire init"
if [[ -n "${ADMIN_URL:-}" ]]; then
    PYTHONPATH=. uv run scire init --admin-url "$ADMIN_URL"
else
    PYTHONPATH=. uv run scire init
fi

echo
echo "Scire installed. Next steps:"
echo "  uv run scire whoami                     # check provider/key status"
echo "  uv run scire config set OPENROUTER_API_KEY sk-...   # add a key"
echo "  uv run scire search \"your topic\"        # first search"
