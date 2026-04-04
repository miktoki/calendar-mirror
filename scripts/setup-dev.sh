#!/usr/bin/env bash
#
# setup-dev.sh — One-time dev machine setup.
#
# Installs bun (if missing), uv (if missing), then wires up the frontend
# and backend ready for local development.
#
# Usage:
#   bash scripts/setup-dev.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── bun ───────────────────────────────────────────────────────────────────────
echo "=== 1/4  bun ==="
if ! command -v bun &>/dev/null; then
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
fi
echo "bun $(bun --version)"

# ── uv ────────────────────────────────────────────────────────────────────────
echo "=== 2/4  uv ==="
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv $(uv --version)"

# ── Frontend deps ─────────────────────────────────────────────────────────────
echo "=== 3/4  Frontend ==="
cd "${REPO_ROOT}/frontend"
bun install

# ── Backend deps ──────────────────────────────────────────────────────────────
echo "=== 4/4  Backend ==="
cd "${REPO_ROOT}/backend"
uv sync

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo "  ⚠  backend/.env created from .env.example — fill in your values before running."
fi

echo ""
echo "✔ Dev setup complete."
echo ""
echo "  Start the backend:   cd backend && uv run uvicorn app:app --reload --port 5000"
echo "  Start the frontend:  cd frontend && bun run dev"
echo ""
echo "  Or build for the Pi: bash scripts/build.sh"
