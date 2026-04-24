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

need_apt=0
for bin in caddy curl; do
    if ! command -v "$bin" &>/dev/null; then
        need_apt=1
        break
    fi
done

if [[ "$need_apt" -eq 1 ]]; then
    echo "=== 1/4  System packages ==="
    # Only refresh apt metadata when we actually need to install something.
    sudo apt-get update -qq
    sudo apt-get install -y caddy curl acl
fi

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &>/dev/null; then
    echo "=== 2/4  uv ==="
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "uv $(uv --version)"
fi

UV_BIN="$(command -v uv || true)"
if [[ -z "${UV_BIN}" ]]; then
    echo "ERROR: uv not found in PATH after install." >&2
    exit 1
fi

# echo "=== 3/4  Backend Python env ==="
cd "${BASE_DIR}/backend"
uv sync -q

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    echo "  ⚠  backend/.env created — fill in GOOGLE_API_KEY and other values before starting."
fi

# echo "=== 4/4  Caddy + systemd ==="
# Install Caddyfile, rewriting any hardcoded /home/pi/rpi-calendar paths to this deploy.
tmp_caddy="$(mktemp)"
sed "s|/home/pi/rpi-calendar|${BASE_DIR}|g" "${BASE_DIR}/Caddyfile" > "${tmp_caddy}"
sudo cp "${tmp_caddy}" /etc/caddy/Caddyfile
rm -f "${tmp_caddy}"
sudo systemctl reload caddy || sudo systemctl restart caddy

# Ensure Caddy can traverse and read the deployed frontend files.
# (403 can happen if any parent dir lacks execute permissions for the caddy user.)
if id caddy &>/dev/null; then
    if command -v setfacl &>/dev/null; then
    parent_dir="$(dirname "${BASE_DIR}")"
        # Grant only the caddy user traverse/read access (tighter than chmod o+...).
    # Important: if the deploy lives under a 0700 home dir, Caddy needs +x on that parent.
    sudo setfacl -m u:caddy:--x "${parent_dir}" || true
        sudo setfacl -m u:caddy:rx "${BASE_DIR}" || true
        sudo setfacl -R -m u:caddy:rx "${BASE_DIR}/frontend" || true
        sudo setfacl -R -d -m u:caddy:rx "${BASE_DIR}/frontend" || true
    else
        # Fallback if ACL tools aren't installed.
        sudo chmod o+x "${BASE_DIR}" || true
        sudo chmod -R o+rX "${BASE_DIR}/frontend" || true
    fi
fi

# Reload once more after permission/ACL changes so Caddy can immediately traverse/read.
sudo systemctl reload caddy || sudo systemctl restart caddy

# Install systemd service(s), rewriting paths to match the deployed BASE_DIR.
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

for svc in "${BASE_DIR}/scripts/systemd/"*.service; do
    svc_name="$(basename "${svc}")"
    # Replace the hardcoded /home/pi/rpi-calendar with the actual deployed path,
    # and set the service user to whoever is running this script.
    svc_user="$(id -un)"
    sed \
        -e "s|/home/pi/rpi-calendar|${BASE_DIR}|g" \
        -e "s|^User=.*$|User=${svc_user}|" \
        -e "s|^ExecStart=uv |ExecStart=${UV_BIN} |" \
    -e "s| -o pi -g pi | -o ${svc_user} -g ${svc_user} |" \
        "${svc}" > "${tmpdir}/${svc_name}"
done

# Ensure the DB directory exists and is writable by the service user.
# (DB_PATH defaults to /var/lib/rpi-calendar/rpi-calendar.db)
sudo mkdir -p /var/lib/rpi-calendar
sudo chmod 0755 /var/lib/rpi-calendar
sudo chown "${svc_user}:${svc_user}" /var/lib/rpi-calendar

sudo cp "${tmpdir}/"*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rpi-calendar-backend.service

echo ""
echo "✔ Setup complete."
echo "  • App (via Caddy): http://raspberrypi.local:8080"
echo ""
echo "  The backend fetches weather automatically on startup and every hour."
echo "  To force a refresh: curl -X POST http://raspberrypi.local:8080/api/weather/refresh"
