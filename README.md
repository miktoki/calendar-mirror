# rpi-calendar

A tablet-optimised calendar and weather display for Raspberry Pi 3B.

- **Calendar** — day, week, and month views sourced from a Google Calendar
- **Weather** — hourly forecast from [api.met.no](https://api.met.no), cached in PocketBase
- **Stack** — SvelteKit (static) + Flask + PocketBase + Caddy

---

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
- PocketBase (embedded database)

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp backend/.env.example backend/.env
```

| Variable                    | Description                                           |
|-----------------------------|-------------------------------------------------------|
| `GOOGLE_API_KEY`            | Google API key with Calendar API enabled (see below)  |
| `CALENDAR_ID`               | Calendar ID to display (default: Norwegian holidays)  |
| `POCKETBASE_URL`            | PocketBase address (default: `http://localhost:8090`) |
| `POCKETBASE_ADMIN_EMAIL`    | PocketBase superuser email                            |
| `POCKETBASE_ADMIN_PASSWORD` | PocketBase superuser password                         |
| `MET_NO_LAT` / `MET_NO_LON` | Coordinates for the weather forecast                  |
| `MET_NO_USER_AGENT`         | Required by met.no — identify your app and contact    |

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

### PocketBase weather collection

After first launch, create a collection named **`weather`** with two fields:

| Field        | Type |
|--------------|------|
| `fetched_at` | Text |
| `forecast`   | JSON |

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

```
VITE_API_BASE=http://localhost:5000
```

---

## Build & deploy to the Pi

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

### 3 — First-time Pi setup

SSH into the Pi and run:

```bash
bash /home/pi/rpi-calendar/scripts/setup-pi.sh
```

This will:
1. Install Caddy, curl, and unzip via apt
2. Install uv if missing
3. Download the latest PocketBase binary for `linux_arm64`
4. Create the Python virtual environment (`uv sync`)
5. Install the Caddyfile and reload Caddy
6. Install and enable the systemd services

### 4 — PocketBase first-run

Visit `http://raspberrypi.local:8090/_/` and create a superuser account.  
Then create the `weather` collection (see [Configuration](#pocketbase-weather-collection) above).

### 5 — Seed weather data

```bash
curl -X POST http://raspberrypi.local:8080/api/weather/refresh
```

---

## Serving

| Service             | Address                            |
|---------------------|------------------------------------|
| App                 | `http://raspberrypi.local:8080`    |
| PocketBase admin UI | `http://raspberrypi.local:8090/_/` |

Caddy serves the static frontend on port 8080 and reverse-proxies `/api/*` to the Flask backend on port 5000.

### Manage services on the Pi

```bash
sudo systemctl status rpi-calendar-backend
sudo systemctl status pocketbase

sudo journalctl -u rpi-calendar-backend -f
sudo journalctl -u pocketbase -f
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
