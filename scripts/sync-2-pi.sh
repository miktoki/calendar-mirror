#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Defaults (override via env vars)
PI_HOST="${PI_HOST:-192.168.0.78}"
PI_USER="${PI_USER:-$(whoami)}"
PI_DEST="${PI_DEST:-/home/${PI_USER}/rpi-calendar}"

NO_BUILD=0
DRY_RUN=0

usage() {
	cat <<EOF
Usage: $(basename "$0") [options]

Deploys a self-contained dist/ folder to the Raspberry Pi and runs the remote setup.

Options:
  -n, --no-build     Skip building dist/
      --dry-run      Print actions but don't rsync/ssh
  -h, --help         Show help

Environment:
  PI_HOST            Raspberry Pi host/IP (default: ${PI_HOST})
  PI_USER            SSH user (default: ${PI_USER})
  PI_DEST            Destination path on Pi (default: ${PI_DEST})
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		-n|--no-build)
			NO_BUILD=1
			shift
			;;
		--dry-run)
			DRY_RUN=1
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Unknown argument: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

if [[ "$NO_BUILD" -eq 0 ]]; then
	"${REPO_ROOT}/scripts/build.sh"
fi

if [[ ! -f "${REPO_ROOT}/dist/scripts/setup-pi.sh" ]]; then
	echo "dist/ is missing scripts/setup-pi.sh. Run scripts/build.sh first." >&2
	exit 1
fi

REMOTE="${PI_USER}@${PI_HOST}"

echo "→ Deploying dist/ to ${REMOTE}:${PI_DEST}/"
echo "→ Running remote setup: ${PI_DEST}/scripts/setup-pi.sh"

if [[ "$DRY_RUN" -eq 1 ]]; then
	exit 0
fi

# dist/ is intended to include everything required on the Pi.
rsync -az --delete "${REPO_ROOT}/dist/" "${REMOTE}:${PI_DEST}/"

# Single remote command to get the Pi up and running.
ssh "${REMOTE}" "bash '${PI_DEST}/scripts/setup-pi.sh'"