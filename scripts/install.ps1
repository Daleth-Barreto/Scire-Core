# Scire one-command install (Windows PowerShell).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# Optionally set $env:ADMIN_URL = "postgresql+psycopg://postgres:pass@localhost:5432/postgres"

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found - installing via pip..."
    python -m pip install --user uv
}

Write-Host "==> installing dependencies (uv sync)"
uv sync

Write-Host "==> running scire init"
if ($env:ADMIN_URL) {
    $env:PYTHONPATH = "."
    uv run scire init --admin-url $env:ADMIN_URL
}
else {
    $env:PYTHONPATH = "."
    uv run scire init
}

Write-Host ""
Write-Host "Scire installed. Next steps:"
Write-Host '  uv run scire whoami                     # check provider/key status'
Write-Host '  uv run scire config set OPENROUTER_API_KEY sk-...   # add a key'
Write-Host '  uv run scire search "your topic"        # first search'
