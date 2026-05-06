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

1. Installs system packages (Caddy, curl)
2. Installs `uv` if missing
3. Creates/updates the backend virtual environment (`uv sync`)
4. Installs the Caddyfile and reloads Caddy
5. Installs and enables the systemd service (`surface-calendar-backend.service`)

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
