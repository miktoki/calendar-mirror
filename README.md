# rpi-calendar

A tablet-optimised calendar and weather display.

- **Calendar** — day, week, and month views sourced from a Google Calendar
- **Weather** — hourly forecast from [api.met.no](https://api.met.no), cached in SQLite
- **Stack** — SvelteKit (static) + FastAPI + SQLite + Caddy

---

## How it’s deployed (mental model)

- Your **dev machine** builds the frontend and assembles a deploy folder (`dist/`).
- That folder is copied to the target machine.
- On the Surface box, a single script (`scripts/setup-surface.sh`) installs system deps + configures Caddy + enables the backend service.

If you only change frontend code, you still need to rebuild on your dev machine and copy files to the target machine.

## Prerequisites

### Development machine

| Tool                             | Purpose                   |
|----------------------------------|---------------------------|
| [Bun](https://bun.sh) ≥ 1.0      | Build the frontend        |
| [uv](https://docs.astral.sh/uv/) | Manage the Python backend |
| rsync                            | Ship the build to the target |

### Surface box

Installed automatically by `setup-surface.sh`:

- Caddy (web server / reverse proxy)
- uv (Python env)
- SQLite (embedded database)

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp backend/.env.example backend/.env
```

| Variable                    | Description                                                                |
|-----------------------------|----------------------------------------------------------------------------|
| `GOOGLE_API_KEY`            | Google API key with Calendar API enabled (see below)                       |
| `CALENDAR_IDS`              | Comma-separated list of calendar IDs (default: Norwegian holidays)         |
| `MET_NO_LAT` / `MET_NO_LON` | Coordinates for the weather forecast                                       |
| `MET_NO_USER_AGENT`         | Required by met.no — identify your app and contact                         |
| `DB_PATH`                   | Path to SQLite DB file (default: `/home/mikaelt/calendar-mirror/calendar.db`)  |

### Database location (SQLite)

By default, the backend stores its SQLite database at:

- `/home/mikaelt/calendar-mirror/calendar.db`

This keeps data stable across deploys.

You can override the location by setting `DB_PATH` in `backend/.env`.

### Getting a Google API key

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Google Calendar API**.
3. Create an **API key** under *APIs & Services → Credentials*.
4. Paste it directly into `backend/.env` as `GOOGLE_API_KEY`.

**Optional — fetch the key programmatically via a service account:**

```bash
# Set SERVICE_ACCOUNT_FILE and API_KEY_NAME in backend/.env first, then:
uv run --directory backend python scripts/fetch_google_api_key.py
```

This writes `GOOGLE_API_KEY` into `backend/.env` automatically.

---

## Development (local)

```bash
bash scripts/setup-dev.sh
```

This installs bun and uv if missing, runs `bun install` for the frontend, `uv sync` for the backend, and copies `backend/.env.example` → `backend/.env` if no `.env` exists yet.

Then start both processes:

```bash
# Backend
cd backend && uv run uvicorn app:app --reload --port 5000

# Frontend (separate terminal)
cd frontend && bun run dev
```

The frontend dev server proxies `/api` to `http://127.0.0.1:5000` by default via Vite. If you want the frontend to call some other backend, set `VITE_API_BASE` in `frontend/.env`:

```env
VITE_API_BASE=http://localhost:5000
```

### Test the built `dist/` app locally

If you want to verify the production-style build on your dev machine, run the backend locally and serve the built frontend as static files.

1. Start the backend:

```bash
cd backend
.venv/bin/uvicorn app:app --port 5000
```

2. Build the deploy folder with the API pointed at your local backend:

```bash
VITE_API_BASE=http://localhost:5000 bash scripts/build.sh
```

3. Serve the built frontend locally:

```bash
cd dist/frontend
python3 -m http.server 4173
```

Then open `http://localhost:4173`.

This is useful for checking that the built app behaves as expected outside the Svelte dev server.

If you want to test with the checked-in Caddy config as well, run:

```bash
FRONTEND_ROOT="$PWD/dist/frontend" BACKEND_ADDR="127.0.0.1:5000" caddy run --config Caddyfile
```

Then open `http://localhost:8080`.

The Caddy config supports local overrides through environment variables:

- `FRONTEND_ROOT` for the static frontend directory
- `BACKEND_ADDR` for the FastAPI backend
- `CADDY_PORT` for the listen port

If you do not set them, it keeps the deploy defaults for the Surface layout.

---

## First-time Surface setup

### 1 — Deploy `dist/` to the Surface box

This repo deploys from a prebuilt folder created on your dev machine.

If you want a one-command deploy from your dev machine, use the helper:

```bash
bash scripts/sync-2-surface.sh
```

That script builds a deploy folder (unless `--no-build`), rsyncs it to `/home/mikaelt/calendar-mirror/dist/`, and runs the remote setup script.

Defaults:

```bash
SURFACE_HOST=surface.local
SURFACE_USER=mikaelt
SURFACE_DIST=/home/mikaelt/calendar-mirror/dist
bash scripts/sync-2-surface.sh
```

Or point it at a custom local deploy directory:

```bash
bash scripts/build.sh --dest ./.deploy/surface
bash scripts/sync-2-surface.sh --no-build --deploy-dir ./.deploy/surface
```

### 2 — One-time setup script on the Surface box

On the target machine, `scripts/setup-surface.sh`:

1. Installs system packages (Caddy, curl, SQLite, WiFi diagnostic tools)
2. Installs `uv` if missing
3. Creates/updates the backend virtual environment (`uv sync`)
4. Installs the Caddyfile and reloads Caddy
5. Installs and enables the systemd services/timers
6. Installs `surface-wifi-monitor`, which logs WiFi failures every 5 minutes

The script is safe to rerun. After it finishes, the app should be reachable at:

- `http://surface.local:8080`

### 3 — Fill in `backend/.env`

If `backend/.env` didn’t exist on the target, the script creates it from `backend/.env.example`.

At minimum, set:

- `GOOGLE_API_KEY`
- `CALENDAR_IDS`
- `MET_NO_USER_AGENT`

Then restart the backend:

```bash
sudo systemctl restart surface-calendar-backend
```

### Surface WiFi diagnostics

The setup script installs a logging-only WiFi monitor on the Surface box:

- systemd timer: `surface-wifi-monitor.timer`
- script: `/usr/local/bin/surface-wifi-monitor`
- log file: `/var/log/surface-wifi-monitor.log`
- config: `/etc/default/surface-wifi-monitor`

It runs every 5 minutes. On failure it records interface state, routes, NetworkManager state, `mwifiex` module parameters, recent NetworkManager logs, recent kernel WiFi messages, default-gateway ping, and an external ping bound to the WiFi interface. Recovery is off by default so the first few failures preserve evidence. To capture a manual snapshot while the device is broken:

If the active interface name starts with `wlx`, the machine is probably using a USB WiFi adapter rather than the internal Surface Marvell adapter. In that case `mwifiex` options can be installed correctly while `/sys/module/mwifiex` is absent; the monitor will still log the active USB device and driver details.

```bash
sudo /usr/local/bin/surface-wifi-monitor --snapshot
```

Useful log commands on the Surface:

```bash
sudo tail -n 200 /var/log/surface-wifi-monitor.log
sudo journalctl -u surface-wifi-monitor.service -n 100 --no-pager
sudo systemctl status surface-wifi-monitor.timer
```

After the monitor has captured at least one failed state, optional recovery can be enabled with:

```bash
sudo sed -i 's/^RECOVERY=.*/RECOVERY=1/' /etc/default/surface-wifi-monitor
sudo systemctl restart surface-wifi-monitor.timer
```

#### One-liner checks for already-applied WiFi fixes

Run these on the Surface box to see exactly what is already in place:

```bash
# WiFi interface and driver
iface=$(iw dev | awk '$1=="Interface"{print $2; exit}'); echo "iface=${iface:-none}"; [[ -n "$iface" ]] && ethtool -i "$iface" 2>/dev/null | sed -n '1,4p'

# Active interface sysfs driver path and USB identity, useful when the interface starts with wlx
iface=$(iw dev | awk '$1=="Interface"{print $2; exit}'); [[ -n "$iface" ]] && { readlink -f "/sys/class/net/$iface/device/driver"; udevadm info -q property -p "/sys/class/net/$iface" | grep -E '^(ID_VENDOR_ID|ID_MODEL_ID|ID_VENDOR=|ID_MODEL=|ID_USB_DRIVER=)'; lsusb; }

# NetworkManager WiFi powersave and MAC randomization config
sudo sh -c 'grep -RHE "wifi\.powersave|wifi\.scan-rand-mac-address|wifi\.cloned-mac-address" /etc/NetworkManager/conf.d /usr/lib/NetworkManager/conf.d 2>/dev/null || true'

# Stored NetworkManager WiFi powersave value for the active connection; 0 means the connection inherits global defaults
nmcli -g GENERAL.CONNECTION device show "$(iw dev | awk '$1=="Interface"{print $2; exit}')" | xargs -r -I{} nmcli -f 802-11-wireless.powersave,802-11-wireless.cloned-mac-address connection show "{}"

# mwifiex deep sleep module option file
sudo sh -c 'grep -RHE "^options[[:space:]]+mwifiex([[:space:]].*)?disable_auto_ds=1" /etc/modprobe.d /usr/lib/modprobe.d 2>/dev/null || true'

# Live mwifiex deep sleep value; Y or 1 means disable_auto_ds is active
cat /sys/module/mwifiex/parameters/disable_auto_ds 2>/dev/null || echo "mwifiex not loaded or parameter missing"

# Invalid/ineffective mwifiex_pcie module options
sudo sh -c 'grep -RHE "^options[[:space:]]+mwifiex_pcie" /etc/modprobe.d /usr/lib/modprobe.d 2>/dev/null || true'

# System sleep targets masked
systemctl is-enabled sleep.target suspend.target hibernate.target hybrid-sleep.target

# X11 blanking state for the current graphical session
DISPLAY=${DISPLAY:-:0} xset q | sed -n '/Screen Saver:/,/DPMS/p'

# XFCE autostart entry for xset blanking/DPMS disable
grep -RHE "xset s off|xset -dpms|xset s noblank" ~/.config/autostart /etc/xdg/autostart 2>/dev/null || true

# Old cron watchdogs
sudo sh -c '(crontab -l 2>/dev/null; find /etc/cron* -type f -maxdepth 2 -print -exec grep -H "wifi-watchdog\|surface-wifi-monitor" {} \; 2>/dev/null) || true'

# New monitor installed and scheduled
systemctl is-enabled surface-wifi-monitor.timer; systemctl status surface-wifi-monitor.timer --no-pager
```

---

## Build & deploy (subsequent updates)

### 1 — Build

Run from the repo root on your development machine:

```bash
bash scripts/build.sh
# or with a custom output path:
bash scripts/build.sh --dest ./.deploy/surface
```

This compiles the SvelteKit frontend and assembles everything into a deploy folder.

### 2 — Ship to the Surface box

```bash
rsync -av dist/ mikaelt@surface.local:/home/mikaelt/calendar-mirror/dist/
```

If you changed `Caddyfile`, `scripts/setup-surface.sh`, or the systemd unit, rerun setup after syncing:

```bash
ssh mikaelt@surface.local 'bash /home/mikaelt/calendar-mirror/dist/scripts/setup-surface.sh'
```

### 5 — Seed weather data

```bash
curl -X POST http://surface.local:8080/api/weather/refresh
```

---

## Serving

| Service             | Address                            |
|---------------------|------------------------------------|
| App                 | `http://surface.local:8080`        |

Caddy serves the static frontend on port 8080 and reverse-proxies `/api/*` to the FastAPI backend on port 5000. By default it assumes the deployed Surface layout where state lives under `/home/mikaelt/calendar-mirror/` and deployed files live under `/home/mikaelt/calendar-mirror/dist/`.

### Manage services on the target

```bash
sudo journalctl -u caddy -f

sudo systemctl status surface-calendar-backend

sudo journalctl -u surface-calendar-backend -f
```

### Subsequent deploys

For normal code-only updates, just sync and restart the backend:

```bash
# On dev machine
bash scripts/sync-2-surface.sh

# On the target
sudo systemctl restart surface-calendar-backend
```

The frontend is static files served by Caddy — no restart needed for frontend-only changes.
