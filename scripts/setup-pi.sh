#!/usr/bin/env bash
#
# setup-pi.sh — Run once on the Raspberry Pi after rsync-ing dist/.
#
# Installs system packages, sets up the backend venv, and enables systemd services.
#
# Run as the pi user (sudo access required for systemd/caddy steps):
#   bash /home/pi/rpi-calendar/scripts/setup-pi.sh
#
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== 1/4  System packages ==="
sudo apt-get update -qq
sudo apt-get install -y caddy curl

echo "=== 2/4  uv ==="
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv $(uv --version)"

echo "=== 3/4  Backend Python env ==="
cd "${BASE_DIR}/backend"
uv sync

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo "  ⚠  backend/.env created — fill in GOOGLE_API_KEY and other values before starting."
fi

echo "=== 4/4  Caddy + systemd ==="
sudo cp "${BASE_DIR}/Caddyfile" /etc/caddy/Caddyfile
sudo systemctl reload caddy || sudo systemctl restart caddy

sudo cp "${BASE_DIR}/scripts/systemd/"*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rpi-calendar-backend.service

echo ""
echo "✔ Setup complete."
echo "  • App (via Caddy): http://raspberrypi.local:8080"
echo ""
echo "  The backend fetches weather automatically on startup and every hour."
echo "  To force a refresh: curl -X POST http://raspberrypi.local:8080/api/weather/refresh"
