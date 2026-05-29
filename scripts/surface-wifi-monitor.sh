#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="${LOG_FILE:-/var/log/surface-wifi-monitor.log}"
STATE_DIR="${STATE_DIR:-/var/lib/surface-wifi-monitor}"
PING_TARGET="${PING_TARGET:-1.1.1.1}"
RECOVERY="${RECOVERY:-0}"

mkdir -p "${STATE_DIR}"
touch "${LOG_FILE}"
chmod 0644 "${LOG_FILE}" 2>/dev/null || true

log() {
	local message="$1"
	printf '%s %s\n' "$(date --iso-8601=seconds)" "${message}" >> "${LOG_FILE}"
	logger -t surface-wifi-monitor -- "${message}"
}

append_cmd() {
	local label="$1"
	shift
	{
		printf '\n--- %s ---\n' "${label}"
		"$@" 2>&1 || true
	} >> "${LOG_FILE}"
}

wifi_iface() {
	if command -v iw >/dev/null 2>&1; then
		iw dev 2>/dev/null | awk '$1 == "Interface" { print $2; exit }'
		return
	fi
	if command -v nmcli >/dev/null 2>&1; then
		nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null | awk -F: '$2 == "wifi" { print $1; exit }'
	fi
}

snapshot() {
	local reason="$1"
	local iface="${2:-}"
	log "snapshot reason=${reason} iface=${iface:-unknown} target=${PING_TARGET} recovery=${RECOVERY}"
	append_cmd "kernel" uname -a
	append_cmd "uptime" uptime
	append_cmd "interfaces" ip -brief address
	append_cmd "routes" ip route
	append_cmd "NetworkManager devices" nmcli device status
	append_cmd "NetworkManager active connections" nmcli -f NAME,UUID,TYPE,DEVICE connection show --active
	if [[ -n "${iface}" ]]; then
		append_cmd "wifi link ${iface}" iw dev "${iface}" link
		append_cmd "iwconfig ${iface}" iwconfig "${iface}"
		append_cmd "driver ${iface}" ethtool -i "${iface}"
		append_cmd "sysfs driver ${iface}" readlink -f "/sys/class/net/${iface}/device/driver"
		append_cmd "udev ${iface}" udevadm info -q property -p "/sys/class/net/${iface}"
	fi
	append_cmd "usb devices" lsusb
	if [[ -e /sys/module/mwifiex/parameters/disable_auto_ds ]]; then
		append_cmd "mwifiex disable_auto_ds" cat /sys/module/mwifiex/parameters/disable_auto_ds
	fi
	append_cmd "mwifiex module parameters" modinfo mwifiex
	append_cmd "recent NetworkManager journal" journalctl -u NetworkManager -n 80 --no-pager
	append_cmd "recent wifi kernel messages" journalctl -k -n 120 --no-pager --grep='mwifiex|wlan|wifi|firmware|NetworkManager'
	append_cmd "ping default gateway" bash -c 'gateway=$(ip route | awk '\''$1 == "default" { print $3; exit }'\''); [[ -n "$gateway" ]] && ping -c 2 -W 3 "$gateway" || echo "no default gateway"'
	if [[ -n "${iface}" ]]; then
		append_cmd "ping target via ${iface}" ping -c 2 -W 5 -I "${iface}" "${PING_TARGET}"
	else
		append_cmd "ping target" ping -c 2 -W 5 "${PING_TARGET}"
	fi
}

recover() {
	local iface="$1"
	log "recovery starting iface=${iface:-unknown}"
	systemctl restart NetworkManager || true
	sleep 15
	if [[ -n "${iface}" ]] && ping -c 2 -W 5 -I "${iface}" "${PING_TARGET}" >/dev/null 2>&1; then
		log "recovery succeeded after NetworkManager restart iface=${iface}"
		return
	fi
	log "recovery reloading mwifiex modules"
	modprobe -r mwifiex_pcie 2>/dev/null || true
	modprobe -r mwifiex_sdio 2>/dev/null || true
	modprobe -r mwifiex 2>/dev/null || true
	modprobe mwifiex || true
	modprobe mwifiex_pcie || true
	systemctl restart NetworkManager || true
}

main() {
	local mode="${1:-check}"
	local iface=""
	iface="$(wifi_iface || true)"

	if [[ "${mode}" == "--snapshot" ]]; then
		snapshot "manual" "${iface}"
		return
	fi

	if [[ -z "${iface}" ]]; then
		log "wifi interface not found"
		snapshot "missing-interface" ""
		return 1
	fi

	if ping -c 2 -W 5 -I "${iface}" "${PING_TARGET}" >/dev/null 2>&1; then
		if [[ -f "${STATE_DIR}/down" ]]; then
			log "wifi recovered iface=${iface} target=${PING_TARGET}"
			rm -f "${STATE_DIR}/down"
		fi
		printf '%s iface=%s target=%s ok\n' "$(date --iso-8601=seconds)" "${iface}" "${PING_TARGET}" > "${STATE_DIR}/last-ok"
		return
	fi

	log "connectivity failed iface=${iface} target=${PING_TARGET}"
	touch "${STATE_DIR}/down"
	snapshot "connectivity-failed" "${iface}"
	if [[ "${RECOVERY}" == "1" ]]; then
		recover "${iface}"
	fi
}

main "$@"