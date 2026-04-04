# Getting Started with Web Development on Raspberry Pi 3B

> **Hardware:** Raspberry Pi 3B · arm64 OS (Raspberry Pi OS Lite 64-bit or Debian arm64)  
> **Assumption:** You have a terminal, internet access during setup, and `uv` already installed.

---

## Step 1 — Decide what you're building

Answer these two questions:

**1. Will your site have server-side logic?** (user input, database reads, dynamic content)
- **No** → you need a **static file server only** → go to [Caddy](#caddy--static-file-server)
- **Yes** → continue to question 2

**2. Do you need a database, authentication, or an admin UI built in?**
- **No** → you're building a standard web app → go to [Flask + SvelteKit](#flask--sveltekit--dynamic-web-app)
- **Yes** → go to [PocketBase + SvelteKit](#pocketbase--sveltekit--full-backend-with-database)

---

## A note on front-end: always use SvelteKit

For any project involving a user interface — whether backed by Flask, FastAPI, or PocketBase — **SvelteKit is the recommended front-end framework**. It compiles down to minimal JavaScript, has no runtime overhead in the browser, and is one of the fastest-growing frameworks in 2025 with strong long-term backing. You build and compile your SvelteKit front-end separately, then serve the compiled output.

SvelteKit works the same way regardless of your back-end choice. The setup steps are included in each section below.

---

## Caddy — Static file server

Use this when your site is entirely pre-built HTML, CSS, and JavaScript (e.g. a compiled SvelteKit static export, a documentation site, or any hand-written front-end with no server-side logic).

### Install Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

### Configure it

Create a `Caddyfile` in your project directory:

```
:8080 {
    root * /home/pi/mysite/build
    file_server
    try_files {path} /index.html
}
```

The `try_files` line ensures SvelteKit's client-side routing works correctly for single-page apps.

### Start serving

```bash
caddy run --config Caddyfile
```

Visit `http://raspberrypi.local:8080` from any device on your local network.

### Set up SvelteKit for static output

On your **development machine** (not the Pi — SvelteKit's build step is too heavy for the Pi 3B):

```bash
npx sv create mysite
cd mysite
npm install
npm install -D @sveltejs/adapter-static
```

Edit `svelte.config.js`:

```js
import adapter from '@sveltejs/adapter-static';

export default {
    kit: {
        adapter: adapter({
            fallback: 'index.html'
        })
    }
};
```

Build and copy to the Pi:

```bash
npm run build
rsync -av build/ pi@raspberrypi.local:/home/pi/mysite/build/
```

Caddy will immediately serve the updated files.

---

## Flask + SvelteKit — Dynamic web app

Use this when you need server-side logic written in Python: processing form data, reading files, calling external APIs, running scripts, or serving dynamic content — but you don't need a built-in database or auth system.

### Set up Flask on the Pi

```bash
uv init myapp
cd myapp
uv add flask
```

Create `app.py`:

```python
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allows SvelteKit dev server to talk to Flask

@app.route('/api/hello')
def hello():
    return jsonify(message='Hello from Flask on the Pi')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

Add CORS support:

```bash
uv add flask-cors
```

Run it:

```bash
uv run app.py
```

### Set up SvelteKit to talk to Flask

On your **development machine**:

```bash
npx sv create myapp-frontend
cd myapp-frontend
npm install
```

In `src/routes/+page.svelte`, fetch from your Pi's Flask API:

```svelte
<script>
    let message = $state('');

    async function load() {
        const res = await fetch('http://raspberrypi.local:5000/api/hello');
        const data = await res.json();
        message = data.message;
    }

    load();
</script>

<p>{message}</p>
```

For local development, run both:
- Flask on the Pi: `uv run app.py`
- SvelteKit on your machine: `npm run dev`

### Deploy to the Pi

When ready to serve everything locally from the Pi, build SvelteKit as a static export (same as the Caddy section above), serve the front-end with Caddy on port 8080, and keep Flask running on port 5000. Caddy can also proxy API calls:

```
:8080 {
    root * /home/pi/myapp-frontend/build
    file_server
    try_files {path} /index.html

    handle /api/* {
        reverse_proxy localhost:5000
    }
}
```

This means your users only ever hit one port.

---

## PocketBase + SvelteKit — Full backend with database

Use this when you want user authentication, a database, file uploads, and an admin dashboard — all without writing backend code. PocketBase gives you all of this as a single binary you just run.

### Install PocketBase on the Pi

```bash
mkdir -p ~/pocketbase && cd ~/pocketbase
curl -L https://github.com/pocketbase/pocketbase/releases/latest/download/pocketbase_linux_arm64.zip \
  -o pocketbase.zip
unzip pocketbase.zip
chmod +x pocketbase
```

> ⚠️ Always use the `linux_arm64` build. The `linux_armv7` build has a known bug in recent versions.

### Start PocketBase

```bash
./pocketbase serve --http="0.0.0.0:8090"
```

On first run, it will prompt you to create a superuser account. Do this, then visit:

- **Admin dashboard:** `http://raspberrypi.local:8090/_/`
- **REST API:** `http://raspberrypi.local:8090/api/`

Create your collections (database tables) and configure auth rules in the admin UI.

### Connect SvelteKit to PocketBase

On your **development machine**:

```bash
npx sv create myapp-frontend
cd myapp-frontend
npm install
npm install pocketbase
```

In `src/lib/pocketbase.js`:

```js
import PocketBase from 'pocketbase';
export const pb = new PocketBase('http://raspberrypi.local:8090');
```

In a page component:

```svelte
<script>
    import { pb } from '$lib/pocketbase';
    let items = $state([]);

    async function load() {
        items = await pb.collection('posts').getFullList();
    }

    load();
</script>

{#each items as item}
    <p>{item.title}</p>
{/each}
```

### Deploy to the Pi

Build SvelteKit and serve with Caddy alongside PocketBase:

```bash
# On your dev machine
npm run build
rsync -av build/ pi@raspberrypi.local:/home/pi/frontend/

# Caddyfile on the Pi
# :8080 {
#     root * /home/pi/frontend
#     file_server
#     try_files {path} /index.html
# }
```

Run PocketBase and Caddy as background services so they survive reboots:

```bash
# PocketBase as a systemd service
sudo nano /etc/systemd/system/pocketbase.service
```

```ini
[Unit]
Description=PocketBase
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/pocketbase
ExecStart=/home/pi/pocketbase/pocketbase serve --http="0.0.0.0:8090"
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable pocketbase
sudo systemctl start pocketbase
```
