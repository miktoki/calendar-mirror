#!/usr/bin/env bash
#
# setup-surface.sh — Configure the deployed Surface instance.
#
# Installs required system packages, prepares the backend environment,
# installs the Caddy config and systemd unit, and fixes frontend read
# permissions so Caddy can serve the built app from dist/.
#
# Usage:
#   bash /home/mikaelt/calendar-mirror/dist/scripts/setup-surface.sh
#
set -euo pipefail

DIST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$(dirname "${DIST_DIR}")"
HOME_DIR="$(dirname "${STATE_DIR}")"

need_apt=0
for bin in caddy curl sqlite3; do
	if ! command -v "$bin" &>/dev/null; then
		need_apt=1
		break
	fi
done

if [[ "$need_apt" -eq 1 ]]; then
	sudo apt-get update -qq
	sudo apt-get install -y caddy curl acl sqlite3
fi

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &>/dev/null; then
	curl -LsSf https://astral.sh/uv/install.sh | sh
fi

UV_BIN="$(command -v uv || true)"
if [[ -z "${UV_BIN}" ]]; then
	echo "ERROR: uv not found in PATH after install." >&2
	exit 1
fi

cd "${DIST_DIR}/backend"
uv sync -q

if [[ ! -f .env ]]; then
	cp .env.example .env
	echo "backend/.env created from .env.example"
fi

tmp_caddy="$(mktemp)"
sed "s|/home/mikaelt/calendar-mirror/dist|${DIST_DIR}|g" "${DIST_DIR}/Caddyfile" > "${tmp_caddy}"
sudo cp "${tmp_caddy}" /etc/caddy/Caddyfile
rm -f "${tmp_caddy}"
sudo systemctl reload caddy || sudo systemctl restart caddy

if id caddy &>/dev/null; then
	if command -v setfacl &>/dev/null; then
		sudo setfacl -m u:caddy:--x "${HOME_DIR}" || true
		sudo setfacl -m u:caddy:--x "${STATE_DIR}" || true
		sudo setfacl -m u:caddy:rx "${DIST_DIR}" || true
		sudo setfacl -R -m u:caddy:rx "${DIST_DIR}/frontend" || true
		sudo setfacl -R -d -m u:caddy:rx "${DIST_DIR}/frontend" || true
	else
		sudo chmod o+x "${HOME_DIR}" || true
		sudo chmod o+x "${STATE_DIR}" || true
		sudo chmod o+rX "${DIST_DIR}" || true
		sudo chmod -R o+rX "${DIST_DIR}/frontend" || true
	fi
fi

sudo systemctl reload caddy || sudo systemctl restart caddy

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT
svc_user="$(id -un)"

for svc in "${DIST_DIR}/scripts/systemd/"*.service; do
	svc_name="$(basename "${svc}")"
	sed \
		-e "s|/home/mikaelt/calendar-mirror/dist|${DIST_DIR}|g" \
		-e "s|^User=.*$|User=${svc_user}|" \
		-e "s|^ExecStart=uv |ExecStart=${UV_BIN} |" \
		"${svc}" > "${tmpdir}/${svc_name}"
done

sudo mkdir -p "${STATE_DIR}"
sudo chmod 0755 "${STATE_DIR}"
sudo chown "${svc_user}:${svc_user}" "${STATE_DIR}"

sudo cp "${tmpdir}/"*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable surface-calendar-backend.service
sudo systemctl restart surface-calendar-backend.service

echo "Setup complete."
echo "App: http://surface.local:8080"
echo "Refresh weather: curl -X POST http://surface.local:8080/api/weather/refresh"