#!/usr/bin/env bash
# moonraker-contrast installer (idempotent, safe to re-run).
#
#   curl -sSL https://raw.githubusercontent.com/jhyland87/moonraker-contrast/v2/install.sh | bash
#
# Overridable via environment:
#   MOONRAKER_VENV    path to Moonraker's virtualenv     (auto-detected)
#   MOONRAKER_CONFIG  printer config dir w/ moonraker.conf (auto-detected)
#   REPO_PATH         where to clone this repo            (~/moonraker-contrast)
#   REPO_URL          git origin
#   REPO_BRANCH       branch to install from             (v2)
#   MOONRAKER_SERVICE systemd service name                (moonraker)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/jhyland87/moonraker-contrast.git}"
REPO_PATH="${REPO_PATH:-${HOME}/moonraker-contrast}"
# TEMPORARY: v2 lives on its own branch. Once v2 merges to main, drop REPO_BRANCH
# and revert the checkout step + primary_branch below back to main.
REPO_BRANCH="${REPO_BRANCH:-v2}"
MOONRAKER_SERVICE="${MOONRAKER_SERVICE:-moonraker}"
MAPPING_NAME="slicer_mappings.cfg"

log()  { printf '\033[0;36m[contrast]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[contrast] WARN:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[contrast] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# --- 1. Detect Moonraker venv ------------------------------------------------
detect_venv() {
    if [ -n "${MOONRAKER_VENV:-}" ]; then echo "$MOONRAKER_VENV"; return; fi
    for cand in "${HOME}/moonraker-env" "${HOME}/moonraker/venv" "${HOME}/.moonraker-env"; do
        [ -x "${cand}/bin/python" ] && { echo "$cand"; return; }
    done
    # Last resort: parse the systemd unit's ExecStart for a python path.
    if command -v systemctl >/dev/null 2>&1; then
        local exe
        exe="$(systemctl show -p ExecStart "${MOONRAKER_SERVICE}" 2>/dev/null \
               | grep -oE '/[^ ]*/bin/python[0-9.]*' | head -n1 || true)"
        if [ -n "$exe" ]; then dirname "$(dirname "$exe")"; return; fi
    fi
    return 1
}

# --- 2. Detect printer config dir --------------------------------------------
detect_config() {
    if [ -n "${MOONRAKER_CONFIG:-}" ]; then echo "$MOONRAKER_CONFIG"; return; fi
    for cand in "${HOME}/printer_data/config" "${HOME}/klipper_config"; do
        [ -f "${cand}/moonraker.conf" ] && { echo "$cand"; return; }
    done
    local found
    found="$(find "${HOME}" -maxdepth 4 -name moonraker.conf 2>/dev/null | head -n1 || true)"
    [ -n "$found" ] && { dirname "$found"; return; }
    return 1
}

VENV="$(detect_venv)"      || die "Could not find Moonraker's venv. Set MOONRAKER_VENV=/path/to/venv and re-run."
CONFIG="$(detect_config)"  || die "Could not find moonraker.conf. Set MOONRAKER_CONFIG=/path/to/config and re-run."
PY="${VENV}/bin/python"
PIP="${VENV}/bin/pip"
[ -x "$PY" ] || die "No python at ${PY}"

log "Moonraker venv:   ${VENV}"
log "Printer config:   ${CONFIG}"

# --- 3. Derive Moonraker components dir from the installed package ------------
COMPONENTS="$("$PY" -c 'import moonraker, os; print(os.path.join(os.path.dirname(moonraker.__file__), "components"))' 2>/dev/null || true)"
[ -n "$COMPONENTS" ] && [ -d "$COMPONENTS" ] \
    || die "Could not locate moonraker/components (is Moonraker installed in ${VENV}?)"
log "Components dir:    ${COMPONENTS}"

# --- 4. Clone or update the repo ---------------------------------------------
if [ -d "${REPO_PATH}/.git" ]; then
    log "Updating existing checkout at ${REPO_PATH} (branch ${REPO_BRANCH})"
    git -C "$REPO_PATH" fetch origin "$REPO_BRANCH" || warn "git fetch failed; continuing with current checkout"
    git -C "$REPO_PATH" checkout "$REPO_BRANCH" || die "Could not check out branch ${REPO_BRANCH} in ${REPO_PATH}"
    git -C "$REPO_PATH" pull --ff-only origin "$REPO_BRANCH" || warn "git pull failed; continuing with current checkout"
else
    log "Cloning ${REPO_URL} (branch ${REPO_BRANCH}) -> ${REPO_PATH}"
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_PATH"
fi

# --- 5. pip install the library (editable so git pull updates take effect) ---
log "Installing moonraker_contrast into the Moonraker venv"
"$PIP" install -e "$REPO_PATH"

# --- 6. Symlink the component shim -------------------------------------------
SHIM_SRC="${REPO_PATH}/component/slicer_compare.py"
[ -f "$SHIM_SRC" ] || die "Shim not found at ${SHIM_SRC}"
ln -sf "$SHIM_SRC" "${COMPONENTS}/slicer_compare.py"
log "Linked component -> ${COMPONENTS}/slicer_compare.py"

# --- 7. Install default mapping (never clobber user edits) -------------------
if [ -f "${CONFIG}/${MAPPING_NAME}" ]; then
    log "Mapping file already present, leaving it untouched: ${CONFIG}/${MAPPING_NAME}"
else
    cp "${REPO_PATH}/mappings/${MAPPING_NAME}" "${CONFIG}/${MAPPING_NAME}"
    log "Installed default mapping -> ${CONFIG}/${MAPPING_NAME}"
fi

# --- 8. Add config sections (grep-guarded for idempotency) -------------------
CONF="${CONFIG}/moonraker.conf"
add_section() {
    local marker="$1" body="$2"
    if grep -qE "^\[${marker}\]" "$CONF" 2>/dev/null; then
        log "moonraker.conf already has [${marker}], skipping"
    else
        printf '\n%s\n' "$body" >> "$CONF"
        log "Added [${marker}] to moonraker.conf"
    fi
}

add_section "slicer_compare" "[slicer_compare]
mapping_path: ${CONFIG}/${MAPPING_NAME}
float_tolerance: 1e-6"

add_section "update_manager moonraker-contrast" "[update_manager moonraker-contrast]
type: git_repo
path: ${REPO_PATH}
origin: ${REPO_URL}
primary_branch: ${REPO_BRANCH}
managed_services: moonraker
install_script: install.sh"

# --- 9. Restart Moonraker ----------------------------------------------------
if command -v systemctl >/dev/null 2>&1 \
   && systemctl list-unit-files 2>/dev/null | grep -q "^${MOONRAKER_SERVICE}\.service"; then
    log "Restarting ${MOONRAKER_SERVICE}"
    sudo systemctl restart "${MOONRAKER_SERVICE}" \
        || warn "Could not restart ${MOONRAKER_SERVICE}; restart it manually."
else
    warn "systemd service '${MOONRAKER_SERVICE}' not found. Restart Moonraker manually to load the plugin."
fi

log "Done. Test it:"
log "  curl -s -X POST 'http://localhost:7125/server/slicer/compare' -H 'Content-Type: application/json' -d '{\"file1\":\"a.gcode\",\"file2\":\"b.gcode\"}' | jq ."
