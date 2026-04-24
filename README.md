# rpi-calendar

## TODOs

- [ ] Clean up in this readme and other docs
- [ ] Make code a bit more compact
- [ ] Add meaningful tests (whatever that means in frontend-land)
- [ ] Calendar fetching is unstable. Fetch and store responses from each calendar independently. Perhaps try to understand why it does not always fetch from all.
- [ ] Difference in styling between hosted in by rpi ()


A tablet-optimised calendar and weather display for Raspberry Pi 3B.

- **Calendar** — day, week, and month views sourced from a Google Calendar
- **Weather** — hourly forecast from [api.met.no](https://api.met.no), cached in SQLite
- **Stack** — SvelteKit (static) + FastAPI + SQLite + Caddy

---

## How it’s deployed (mental model)

- Your **dev machine** builds the frontend and assembles a deploy folder (`dist/`).
- That folder is copied to the **Raspberry Pi**.
- On the Pi, a single script (`scripts/setup-pi.sh`) installs system deps + configures Caddy + enables the backend service.

If you only change frontend code, you still need to rebuild on your dev machine and copy files to the Pi.

## Prerequisites

### Development machine

| Tool                             | Purpose                   |
|----------------------------------|---------------------------|
| [Bun](https://bun.sh) ≥ 1.0      | Build the frontend        |
| [uv](https://docs.astral.sh/uv/) | Manage the Python backend |
| rsync                            | Ship the build to the Pi  |

### Raspberry Pi

Installed automatically by `setup-pi.sh`:

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
| `DB_PATH`                   | Path to SQLite DB file (default: `/var/lib/rpi-calendar/rpi-calendar.db`)  |

### Database location (SQLite)

By default, the backend stores its SQLite database at:

- `/var/lib/rpi-calendar/rpi-calendar.db`

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

The frontend dev server proxies nothing — set `VITE_API_BASE` in `frontend/.env`:

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

The Caddy config now supports local overrides through environment variables:

- `FRONTEND_ROOT` for the static frontend directory
- `BACKEND_ADDR` for the FastAPI backend
- `CADDY_PORT` for the listen port

If you do not set them, it keeps the Raspberry Pi defaults.

---

## First-time Raspberry Pi setup

### 1 — Deploy `dist/` to the Pi

This repo is set up to deploy from a prebuilt `dist/` folder (built on your dev machine).

If you want a one-command deploy from your dev machine, use the helper:

```bash
bash scripts/sync-2-pi.sh
```

That script builds (unless `--no-build`), rsyncs **only `dist/`** to the Pi, and runs the Pi setup script.

You can override where it deploys by setting env vars:

```bash
PI_HOST=raspberrypi.local
PI_USER=pi
PI_DEST=/home/pi/rpi-calendar
bash scripts/sync-2-pi.sh
```

### 2 — One-time setup script on the Pi

On the Pi, `scripts/setup-pi.sh`:

1. Installs system packages (Caddy, curl)
2. Installs `uv` if missing
3. Creates/updates the backend virtual environment (`uv sync`)
4. Installs the Caddyfile and reloads Caddy
5. Installs and enables the systemd service (`rpi-calendar-backend.service`)

After it finishes, the app should be reachable at:

- `http://raspberrypi.local:8080`

### 3 — Fill in `backend/.env`

If `backend/.env` didn’t exist on the Pi, the script creates it from `backend/.env.example`.

At minimum, set:

- `GOOGLE_API_KEY`
- `CALENDAR_IDS`
- `MET_NO_USER_AGENT`

Then restart the backend:

```bash
sudo systemctl restart rpi-calendar-backend
```

---

## Build & deploy (subsequent updates)

### 1 — Build

Run from the repo root on your development machine:

```bash
bash scripts/build.sh
# or with a custom output path:
bash scripts/build.sh --dest /tmp/rpi-dist
```

This compiles the SvelteKit frontend and assembles everything into `dist/`.

### 2 — Ship to the Pi

```bash
rsync -av dist/ pi@raspberrypi.local:/home/pi/rpi-calendar/
```

### 5 — Seed weather data

```bash
curl -X POST http://raspberrypi.local:8080/api/weather/refresh
```

---

## Serving

| Service             | Address                            |
|---------------------|------------------------------------|
| App                 | `http://raspberrypi.local:8080`    |

Caddy serves the static frontend on port 8080 and reverse-proxies `/api/*` to the FastAPI backend on port 5000. By default it uses the Pi paths, but you can override them with `FRONTEND_ROOT`, `BACKEND_ADDR`, and `CADDY_PORT` when running it locally.

### Manage services on the Pi

```bash
sudo systemctl status rpi-calendar-backend

sudo journalctl -u rpi-calendar-backend -f
```

### Subsequent deploys

No re-setup needed after the first time — just rsync and restart:

```bash
# On dev machine
bash scripts/build.sh
rsync -av dist/ pi@raspberrypi.local:/home/pi/rpi-calendar/

# On the Pi
sudo systemctl restart rpi-calendar-backend
```

The frontend is static files served by Caddy — no restart needed for frontend-only changes.
