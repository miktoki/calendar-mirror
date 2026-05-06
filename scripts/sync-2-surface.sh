#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SURFACE_HOST="${SURFACE_HOST:-surface.local}"
SURFACE_USER="${SURFACE_USER:-mikaelt}"
SURFACE_DIST="${SURFACE_DIST:-/home/${SURFACE_USER}/calendar-mirror/dist}"
DEPLOY_DIR="${DEPLOY_DIR:-${REPO_ROOT}/dist}"

NO_BUILD=0
DRY_RUN=0

usage() {
	cat <<EOF
Usage: $(basename "$0") [options]

Builds and syncs the deploy directory to the Surface box, then runs remote setup.
The final SSH step allocates a TTY so sudo on the remote host can prompt.
Frontend-only deploys skip remote setup.

Options:
	-n, --no-build     Skip building the deploy directory
	--deploy-dir       Local deploy directory to rsync (default: ${DEPLOY_DIR})
	--dry-run          Print actions but don't rsync/ssh
	-h, --help         Show help

Environment:
	SURFACE_HOST       SSH host (default: ${SURFACE_HOST})
	SURFACE_USER       SSH user (default: ${SURFACE_USER})
	SURFACE_DIST       Remote deploy directory (default: ${SURFACE_DIST})
	DEPLOY_DIR         Local deploy directory (default: ${DEPLOY_DIR})
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		-n|--no-build)
			NO_BUILD=1
			shift
			;;
		--deploy-dir)
			DEPLOY_DIR="$2"
			shift 2
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
	"${REPO_ROOT}/scripts/build.sh" --dest "${DEPLOY_DIR}"
fi

if [[ ! -f "${DEPLOY_DIR}/scripts/setup-surface.sh" ]]; then
	echo "${DEPLOY_DIR} is missing scripts/setup-surface.sh. Run scripts/build.sh first." >&2
	exit 1
fi

REMOTE="${SURFACE_USER}@${SURFACE_HOST}"

echo "→ Deploying ${DEPLOY_DIR}/ to ${REMOTE}:${SURFACE_DIST}/"

if [[ "$DRY_RUN" -eq 1 ]]; then
	exit 0
fi

ssh "${REMOTE}" "mkdir -p '$(dirname "${SURFACE_DIST}")'"

change_list="$(rsync -acni --delete --out-format='%n' "${DEPLOY_DIR}/" "${REMOTE}:${SURFACE_DIST}/")"
needs_setup=0
has_changes=0

while IFS= read -r path; do
	if [[ -z "${path}" ]]; then
		continue
	fi
	has_changes=1
	if [[ "${path}" != frontend/* ]]; then
		needs_setup=1
		break
	fi
done <<< "${change_list}"

rsync -az --delete "${DEPLOY_DIR}/" "${REMOTE}:${SURFACE_DIST}/"

if [[ "${has_changes}" -eq 0 ]]; then
	echo "→ No remote changes detected"
	elif [[ "${needs_setup}" -eq 0 ]]; then
	echo "→ Frontend-only changes detected; skipping remote setup"
else
	echo "→ Running remote setup: ${SURFACE_DIST}/scripts/setup-surface.sh"
	ssh -t "${REMOTE}" "bash '${SURFACE_DIST}/scripts/setup-surface.sh'"
fi