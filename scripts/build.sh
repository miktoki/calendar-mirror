#!/usr/bin/env bash
#
# build.sh — Build frontend and assemble a deployable folder.
#
# Usage:
#   ./scripts/build.sh [--dest <path>]  (default: ./dist)
#
# The resulting folder can be rsync'd to the Pi:
#   rsync -av dist/ mikaelt@surface.local:/home/mikaelt/calendar-mirror/dist/
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-${REPO_ROOT}/dist}"

# Allow --dest flag
if [[ "${1:-}" == "--dest" && -n "${2:-}" ]]; then
    DEST="$2"
fi

echo "→ Building into: ${DEST}"
rm -rf "${DEST}"
mkdir -p "${DEST}"

# ── Frontend ─────────────────────────────────────────────────────────────────
# echo "→ Building SvelteKit frontend..."
cd "${REPO_ROOT}/frontend"
bun install --silent
set +e
bun run --silent build -l error -- --logLevel error 2>&1 | grep -Ev \
    -e '^Run npm run preview' \
    -e '^> Using @sveltejs/adapter-static' \
    -e '^\s*Wrote site to "build"' \
    -e '^\s*✔ done' \
    -e '^\s*$'
build_rc=${PIPESTATUS[0]}
set -e
if [[ ${build_rc} -ne 0 ]]; then
    exit "${build_rc}"
fi
mkdir -p "${DEST}/frontend"
cp -r build/. "${DEST}/frontend/"

# ── Backend ──────────────────────────────────────────────────────────────────
# echo "→ Copying FastAPI backend..."
mkdir -p "${DEST}/backend"
cp "${REPO_ROOT}/backend/app.py"         "${DEST}/backend/"
cp "${REPO_ROOT}/backend/db.py"         "${DEST}/backend/"
cp "${REPO_ROOT}/backend/pyproject.toml" "${DEST}/backend/"
cp "${REPO_ROOT}/backend/uv.lock"        "${DEST}/backend/"
cp "${REPO_ROOT}/backend/.env.example"   "${DEST}/backend/.env.example"
if [[ -f "${REPO_ROOT}/backend/.env" ]]; then
    cp "${REPO_ROOT}/backend/.env" "${DEST}/backend/.env"
fi

# ── Helper scripts ────────────────────────────────────────────────────────────
# echo "→ Copying helper scripts..."
mkdir -p "${DEST}/scripts"
cp "${REPO_ROOT}/scripts/fetch_google_api_key.py" "${DEST}/scripts/"
cp "${REPO_ROOT}/scripts/setup-surface.sh"        "${DEST}/scripts/"

# ── Caddy config ─────────────────────────────────────────────────────────────
# echo "→ Copying Caddyfile..."
cp "${REPO_ROOT}/Caddyfile" "${DEST}/Caddyfile"

# ── Systemd units ────────────────────────────────────────────────────────────
# echo "→ Copying systemd units..."
mkdir -p "${DEST}/scripts/systemd"
cp "${REPO_ROOT}/scripts/systemd/"*.service "${DEST}/scripts/systemd/"

# echo ""
# echo "✔ Done. Deploy to the Pi with:"
# echo "  rsync -av '${DEST}/' mikaelt@surface.local:/home/mikaelt/calendar-mirror/dist/"
# echo "  Then on the target: bash /home/mikaelt/calendar-mirror/dist/scripts/setup-surface.sh"
