#!/usr/bin/env python3
"""
Fetch the Google API key via a service account and write it to backend/.env.

This is a one-off helper script, not part of the main app.
It requires the 'fetch-key' extra:

    uv run --extra fetch-key python scripts/fetch_google_api_key.py

Required .env variables (read from backend/.env)
-----------------------
SERVICE_ACCOUNT_FILE  - path to the service account JSON key file
API_KEY_NAME          - full resource name of the API key:
                        projects/<project-number>/locations/global/keys/<uuid>
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(ENV_PATH)

_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_ENDPOINT = "https://apikeys.googleapis.com/v2/{name}/keyString"


def fetch_key(sa_file: str, key_name: str) -> str:
    try:
        import google.auth.transport.requests
        from google.oauth2 import service_account
    except ImportError:
        print(
            "ERROR: google-auth is not installed.\n"
            "Install the fetch-key extra first:\n\n"
            "    uv run --extra fetch-key python google_api_key.py\n",
            file=sys.stderr,
        )
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_file(
        sa_file, scopes=[_SCOPE]
    )
    credentials.refresh(google.auth.transport.requests.Request())

    req = urllib.request.Request(
        _ENDPOINT.format(name=key_name),
        headers={"Authorization": f"Bearer {credentials.token}"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    return data["keyString"]


if __name__ == "__main__":
    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE") or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    key_name = os.environ.get("API_KEY_NAME")

    if not sa_file or not key_name:
        print(
            "ERROR: Set SERVICE_ACCOUNT_FILE and API_KEY_NAME in .env first.",
            file=sys.stderr,
        )
        sys.exit(1)

    key = fetch_key(sa_file, key_name)

    set_key(str(ENV_PATH), "GOOGLE_API_KEY", key)
    print(f"GOOGLE_API_KEY written to {ENV_PATH}")
