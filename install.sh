#!/usr/bin/env bash
# moonraker-contrast installer (idempotent, safe to re-run).
#
#   curl -sSL https://raw.githubusercontent.com/jhyland87/moonraker-contrast/v2/install.sh | bash
#
# Works on a standard Debian/Raspberry Pi Klipper install and on embedded
# printers running the Creality Helper Script (K1/K1C/K2, Buildroot + init.d),
# which put everything under /usr/data instead of $HOME.
#
# Overridable via environment:
#   MOONRAKER_VENV       Moonraker's virtualenv               (auto-detected)
#   MOONRAKER_CONFIG     printer config dir w/ moonraker.conf (auto-detected)
#   MOONRAKER_COMPONENTS moonraker/components dir             (auto-detected)
#   MOONRAKER_PLATFORM   'embedded' or 'standard'             (auto-detected)
#   REPO_PATH            where to clone this repo             (beside printer_data)
#   REPO_URL             git origin
#   REPO_BRANCH          branch to install from               (v2)
#   MOONRAKER_SERVICE    systemd service name                 (moonraker)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/jhyland87/moonraker-contrast.git}"
# TEMPORARY: v2 lives on its own branch. Once v2 merges to main, drop REPO_BRANCH
# and revert the checkout step + primary_branch below back to main.
REPO_BRANCH="${REPO_BRANCH:-v2}"
MOONRAKER_SERVICE="${MOONRAKER_SERVICE:-moonraker}"
OS_RELEASE_FILE="${OS_RELEASE_FILE:-/etc/os-release}"
MAPPING_NAME="slicer_mappings.cfg"

log()  { printf '\033[0;36m[contrast]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[contrast] WARN:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[contrast] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Run as root where we already are (embedded printers), sudo elsewhere. On a
# Creality printer /usr/bin/sudo is a shim the helper script installs.
maybe_sudo() {
    if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        "$@"
    fi
}

# --- 1. Identify the platform ------------------------------------------------
# Creality's firmware is Buildroot; a normal Klipper host is debian/ubuntu/etc.
# This only picks which candidate paths are tried first -- both sets are always
# tried, so an unrecognised distro still resolves.
detect_platform() {
    if [ -n "${MOONRAKER_PLATFORM:-}" ]; then echo "$MOONRAKER_PLATFORM"; return; fi
    local ids=""
    if [ -r "$OS_RELEASE_FILE" ]; then
        # Subshell: os-release sets NAME/VERSION/... which we don't want here.
        # shellcheck source=/dev/null
        ids="$( . "$OS_RELEASE_FILE" >/dev/null 2>&1 || true
                printf '%s %s' "${ID:-}" "${ID_LIKE:-}" )"
    fi
    case "$ids" in
        *buildroot*) echo "embedded" ;;
        *)           echo "standard" ;;
    esac
}
PLATFORM="$(detect_platform)"

if [ "$PLATFORM" = "embedded" ]; then
    VENV_CANDIDATES=("/usr/data/moonraker/moonraker-env" "${HOME}/moonraker-env" \
                     "${HOME}/moonraker/venv" "${HOME}/.moonraker-env")
    CONFIG_CANDIDATES=("/usr/data/printer_data/config" "${HOME}/printer_data/config" \
                       "${HOME}/klipper_config")
    COMPONENT_CANDIDATES=("/usr/data/moonraker/moonraker/moonraker/components" \
                          "${HOME}/moonraker/moonraker/components")
    SEARCH_ROOTS=("/usr/data" "${HOME}")
else
    VENV_CANDIDATES=("${HOME}/moonraker-env" "${HOME}/moonraker/venv" \
                     "${HOME}/.moonraker-env" "/usr/data/moonraker/moonraker-env")
    CONFIG_CANDIDATES=("${HOME}/printer_data/config" "${HOME}/klipper_config" \
                       "/usr/data/printer_data/config")
    COMPONENT_CANDIDATES=("${HOME}/moonraker/moonraker/components" \
                          "/usr/data/moonraker/moonraker/moonraker/components")
    SEARCH_ROOTS=("${HOME}" "/usr/data")
fi

# --- 2. Find Moonraker's command line ----------------------------------------
# One probe answers three questions: which python, which source tree, which data
# dir. E.g. on a K1C:
#   /usr/data/moonraker/moonraker-env/bin/python \
#     /usr/data/moonraker/moonraker/moonraker/moonraker.py -d /usr/data/printer_data
probe_moonraker_cmdline() {
    local ps_out matches candidate py line unit
    line=""
    # a) The running server -- authoritative, and Moonraker is up during installs.
    #    busybox ps rejects most flags, so degrade to bare `ps`.
    ps_out="$(ps -ef 2>/dev/null || true)"
    [ -n "$ps_out" ] || ps_out="$(ps w 2>/dev/null || true)"
    [ -n "$ps_out" ] || ps_out="$(ps 2>/dev/null || true)"
    matches="$(printf '%s\n' "$ps_out" \
               | grep -E 'moonraker\.py|-m[[:space:]]+moonraker' || true)"
    # Other processes can merely *mention* moonraker.py (an editor, the shell
    # running this installer), so prefer a line that names a real interpreter.
    if [ -n "$matches" ]; then
        while IFS= read -r candidate; do
            [ -n "$candidate" ] || continue
            if [ -z "$line" ]; then line="$candidate"; fi
            py="$(printf '%s' "$candidate" | grep -oE '/[^ "]*/bin/python[0-9.]*' | head -n1 || true)"
            if [ -n "$py" ] && [ -x "$py" ]; then line="$candidate"; break; fi
        done <<< "$matches"
    fi
    # b) systemd unit.
    if [ -z "$line" ] && command -v systemctl >/dev/null 2>&1; then
        line="$(systemctl show -p ExecStart "${MOONRAKER_SERVICE}" 2>/dev/null || true)"
    fi
    # c) init.d script. Best-effort: it may reference paths through variables.
    if [ -z "$line" ]; then
        for unit in /etc/init.d/S*moonraker* /etc/init.d/moonraker; do
            [ -f "$unit" ] || continue
            line="$(grep -h '/bin/python' "$unit" 2>/dev/null | head -n1 || true)"
            [ -n "$line" ] && break
        done
    fi
    printf '%s' "$line"
}

# Probed once -- the readers below run in subshells, so a lazy cache wouldn't stick.
MOONRAKER_CMDLINE="$(probe_moonraker_cmdline)"

# -e so a pattern starting with `-` isn't read as an option.
cmdline_field() { printf '%s' "$MOONRAKER_CMDLINE" | grep -oE -e "$1" | head -n1 || true; }
cmdline_python()   { cmdline_field '/[^ "]*/bin/python[0-9.]*'; }
cmdline_script()   { cmdline_field '/[^ "]*/moonraker\.py'; }
cmdline_datapath() { cmdline_field '\-d[[:space:]]+[^ "]+' | sed -E 's/^-d[[:space:]]+//'; }

# --- 3. Detect venv / config / components ------------------------------------
detect_venv() {
    if [ -n "${MOONRAKER_VENV:-}" ]; then echo "$MOONRAKER_VENV"; return; fi
    local py cand
    py="$(cmdline_python)"
    # <venv>/bin/python -> <venv>
    if [ -n "$py" ] && [ -x "$py" ]; then dirname "$(dirname "$py")"; return; fi
    for cand in "${VENV_CANDIDATES[@]}"; do
        [ -x "${cand}/bin/python" ] && { echo "$cand"; return; }
    done
    return 1
}

detect_config() {
    if [ -n "${MOONRAKER_CONFIG:-}" ]; then echo "$MOONRAKER_CONFIG"; return; fi
    local data cand root found
    data="$(cmdline_datapath)"
    if [ -n "$data" ] && [ -f "${data}/config/moonraker.conf" ]; then
        echo "${data}/config"; return
    fi
    for cand in "${CONFIG_CANDIDATES[@]}"; do
        [ -f "${cand}/moonraker.conf" ] && { echo "$cand"; return; }
    done
    for root in "${SEARCH_ROOTS[@]}"; do
        [ -d "$root" ] || continue
        found="$(find "$root" -maxdepth 4 -name moonraker.conf 2>/dev/null | head -n1 || true)"
        [ -n "$found" ] && { dirname "$found"; return; }
    done
    return 1
}

# Moonraker installed as a package (standard installs) can just say where it is.
components_from_import() {
    local dir
    dir="$("$PY" -c 'import moonraker, os; print(os.path.join(os.path.dirname(moonraker.__file__), "components"))' 2>/dev/null || true)"
    [ -n "$dir" ] && [ -d "$dir" ] && echo "$dir"
}

# Run-from-source: <src>/moonraker/moonraker.py -> <src>/moonraker/components.
# This is how Creality printers run it, where the import above always fails.
components_from_script() {
    local script dir
    script="$(cmdline_script)"
    [ -n "$script" ] || return 0
    dir="$(dirname "$script")/components"
    [ -d "$dir" ] && echo "$dir"
}

detect_components() {
    if [ -n "${MOONRAKER_COMPONENTS:-}" ]; then echo "$MOONRAKER_COMPONENTS"; return; fi
    local dir cand
    if [ "$PLATFORM" = "embedded" ]; then
        dir="$(components_from_script)"; [ -n "$dir" ] && { echo "$dir"; return; }
        dir="$(components_from_import)"; [ -n "$dir" ] && { echo "$dir"; return; }
    else
        dir="$(components_from_import)"; [ -n "$dir" ] && { echo "$dir"; return; }
        dir="$(components_from_script)"; [ -n "$dir" ] && { echo "$dir"; return; }
    fi
    for cand in "${COMPONENT_CANDIDATES[@]}"; do
        [ -d "$cand" ] && { echo "$cand"; return; }
    done
    return 1
}

VENV="$(detect_venv)"      || die "Could not find Moonraker's venv. Set MOONRAKER_VENV=/path/to/venv and re-run."
CONFIG="$(detect_config)"  || die "Could not find moonraker.conf. Set MOONRAKER_CONFIG=/path/to/config and re-run."
PY="${VENV}/bin/python"
PIP="${VENV}/bin/pip"
[ -x "$PY" ] || die "No python at ${PY}"
COMPONENTS="$(detect_components)" \
    || die "Could not locate moonraker/components. Set MOONRAKER_COMPONENTS=/path/to/components and re-run."

# Clone beside the data dir: /usr/data/printer_data/config -> /usr/data, so an
# embedded printer gets the repo on its big partition rather than in /root.
repo_parent() {
    local parent
    parent="$(dirname "$CONFIG")"
    case "$(basename "$parent")" in
        *printer*data*|*_data) dirname "$parent" ;;
        *)                     echo "${HOME}" ;;
    esac
}
REPO_PATH="${REPO_PATH:-$(repo_parent)/moonraker-contrast}"

log "Platform:          ${PLATFORM}"
log "Moonraker venv:    ${VENV}"
log "Printer config:    ${CONFIG}"
log "Components dir:    ${COMPONENTS}"
log "Repo path:         ${REPO_PATH}"

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

# --- 5. Put moonraker_contrast on Moonraker's import path --------------------
# Editable install so git pull updates take effect without reinstalling.
log "Installing moonraker_contrast into ${VENV}"
if [ -x "$PIP" ]; then
    "$PIP" install -e "$REPO_PATH" || warn "pip install failed"
elif "$PY" -m pip --version >/dev/null 2>&1; then
    "$PY" -m pip install -e "$REPO_PATH" || warn "pip install failed"
else
    warn "No pip found in ${VENV}"
fi

if ! "$PY" -c 'import moonraker_contrast' >/dev/null 2>&1; then
    # Old pip/setuptools can't do a PEP 660 editable install of a pyproject-only
    # package. Ours is pure-stdlib with no dependencies, so a path file does.
    SITE_DIR="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' 2>/dev/null || true)"
    [ -n "$SITE_DIR" ] && [ -d "$SITE_DIR" ] \
        || die "pip install failed and site-packages for ${PY} could not be located"
    printf '%s\n' "${REPO_PATH}/src" > "${SITE_DIR}/moonraker-contrast.pth"
    log "Added ${SITE_DIR}/moonraker-contrast.pth -> ${REPO_PATH}/src"
    "$PY" -c 'import moonraker_contrast' >/dev/null 2>&1 \
        || die "moonraker_contrast is still not importable by ${PY}"
fi

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
restart_initd() {
    local unit
    for unit in /etc/init.d/S*moonraker* /etc/init.d/moonraker; do
        [ -x "$unit" ] || continue
        log "Restarting ${unit}"
        # The Creality helper script stops and starts Moonraker rather than
        # calling `restart`; mirror what's known to work there.
        maybe_sudo "$unit" stop || true
        sleep 1
        maybe_sudo "$unit" start || return 1
        return 0
    done
    return 1
}

restart_systemd() {
    command -v systemctl >/dev/null 2>&1 || return 1
    systemctl list-unit-files 2>/dev/null | grep -q "^${MOONRAKER_SERVICE}\.service" || return 1
    log "Restarting ${MOONRAKER_SERVICE}"
    maybe_sudo systemctl restart "${MOONRAKER_SERVICE}" || return 1
    return 0
}

if [ "$PLATFORM" = "embedded" ]; then
    restart_initd || restart_systemd \
        || warn "Could not restart Moonraker; restart it manually to load the plugin."
else
    restart_systemd || restart_initd \
        || warn "Could not restart Moonraker; restart it manually to load the plugin."
fi

log "Done. Test it:"
log "  curl -s -X POST 'http://localhost:7125/server/slicer/compare' -H 'Content-Type: application/json' -d '{\"file1\":\"a.gcode\",\"file2\":\"b.gcode\"}' | jq ."
