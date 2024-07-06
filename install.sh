#!/usr/bin/env sh

MOONRAKER_CONF="/usr/data/printer_data/config/moonraker.conf"
MOONRAKER_BASE="/usr/data/moonraker/moonraker"

# moonraker/components
_err(){
	printf "ERROR: %s\n" "${1}"

	test $2 && exit $2
}


test -f "${MOONRAKER_CONF}" || _err "No moonraker config found at ${MOONRAKER_CONF}" 1
test -d "${MOONRAKER_BASE}" || _err "No moonraker directory found at ${MOONRAKER_BASE}" 1

grep -qE '^\[slicer\]$' "${MOONRAKER_CONF}" || echo -e "\n[slicer]" >> "${MOONRAKER_CONF}"


cp -Rv ./src/components "${MOONRAKER_BASE}/moonraker/"