# moonraker-contrast

A [Moonraker](https://github.com/Arksine/moonraker) plugin that compares the
**slicer settings** embedded in two gcode files stored on your printer and
returns a `diff`-style result over Moonraker's HTTP **and** websocket API.

It understands the slic3r-engine family of slicers — **PrusaSlicer,
SuperSlicer, OrcaSlicer, BambuStudio, BambuSlicer** — including the fact that
they store their config in different places (Prusa family in the file footer,
Bambu in the header) and name/scale the same logical setting differently.
Equivalent-but-renamed settings (e.g. *first layer height* vs *initial layer
print height*, or an inverted *elephant foot compensation* vs *xy contour
compensation*) are aligned through a **user-editable mapping file**.

> Cura is intentionally **not** supported — it does not embed its full settings
> in the gcode by default, so there is nothing to compare.

## Install

On the machine running Moonraker — a Raspberry Pi / Debian host, or a Creality
printer running the [Creality Helper Script](https://github.com/Guilouz/Creality-Helper-Script)
(K1/K1C/K2), where everything lives under `/usr/data` instead of `$HOME`:

```sh
curl -sSL https://raw.githubusercontent.com/jhyland87/moonraker-contrast/v2/install.sh | bash
```

The installer is idempotent (safe to re-run). It:

1. identifies the platform (`/etc/os-release`) and finds Moonraker's virtualenv,
   config dir, and components dir — primarily by reading the running Moonraker
   process's command line, falling back to the known layouts for each platform,
2. clones this repo beside your `printer_data` dir (`~/moonraker-contrast`, or
   `/usr/data/moonraker-contrast` on a Creality printer),
3. `pip install -e`'s the `moonraker_contrast` library into the venv (falling
   back to a `.pth` path file where pip is too old for an editable install),
4. symlinks the component into `moonraker/components/`,
5. installs a default `slicer_mappings.cfg` into your config dir (never
   overwriting an existing one),
6. adds `[slicer_compare]` and an `[update_manager moonraker-contrast]` section
   to `moonraker.conf`,
7. restarts Moonraker (`systemctl` on a standard host,
   `/etc/init.d/S56moonraker_service` on a Creality printer).

Override detection with env vars if needed: `MOONRAKER_VENV`, `MOONRAKER_CONFIG`,
`MOONRAKER_COMPONENTS`, `MOONRAKER_PLATFORM` (`embedded`/`standard`), `REPO_PATH`,
`REPO_BRANCH`, `MOONRAKER_SERVICE`.

## API

Both endpoints are exposed over the HTTP REST API and the JSON-RPC websocket.

### `POST /server/slicer/compare`

| param          | type   | notes                                   |
| -------------- | ------ | --------------------------------------- |
| `file1`        | string | gcode path relative to the gcodes root  |
| `file2`        | string | gcode path relative to the gcodes root  |
| `include_same` | bool   | optional; include unchanged values too  |

```sh
curl -s -X POST 'http://PRINTER:7125/server/slicer/compare' \
  -H 'Content-Type: application/json' \
  -d '{"file1":"a.gcode","file2":"b.gcode"}' | jq .
```

Response (abridged):

```json
{
  "left":  {"file":"a.gcode","slicer":"PrusaSlicer","version":"2.7.1","partial":false},
  "right": {"file":"b.gcode","slicer":"OrcaSlicer","version":"2.1.0","partial":false},
  "summary": {"same":412,"changed":9,"only_left":3,"only_right":5},
  "changed": {
    "first_layer_height": {
      "left":  {"value":0.2,"raw_key":"first_layer_height"},
      "right": {"value":0.3,"raw_key":"initial_layer_print_height"},
      "canonical": true
    }
  },
  "only_left":  {"...": {"value": 1, "raw_key": "..."}},
  "only_right": {"...": {"value": 3, "raw_key": "..."}},
  "same_keys": ["layer_height", "..."],
  "warnings": []
}
```

`raw_key` always tells you which actual per-slicer option each side came from.
`canonical: true` marks a setting aligned via the mapping file; `false` marks a
plain same-name comparison.

### `GET /server/slicer/settings?file=a.gcode`

Returns the parsed `raw`, `canonical`, and `passthrough` views for a single
file — handy for debugging mappings.

Websocket equivalents use the derived method names `server.slicer.compare` and
`server.slicer.settings`.

## Adding / changing setting mappings

Edit `slicer_mappings.cfg` in your config dir — `~/printer_data/config/` on a
standard install, `/usr/data/printer_data/config/` on a Creality printer (INI,
same format as `moonraker.conf`). Changes take effect immediately — no restart needed.

```ini
[canonical elephant_foot_compensation]
prusaslicer = elefant_foot_compensation
orcaslicer  = elefant_foot_compensation
bambustudio = xy_contour_compensation | invert_number
```

Each `[canonical <name>]` section declares one logical setting; each line maps a
slicer's raw key to it, with an optional value transform (`invert_number`,
`invert_bool`, `as_bool`, `percent_to_float`, `float_to_percent`, `scale:<f>`).
Settings with no mapping are still compared — but only against the same raw key
on the other file. See the comments in the shipped file for the full reference.

## Development

The `moonraker_contrast` library is pure-stdlib and fully testable without
Moonraker installed:

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

The Moonraker component (`component/slicer_compare.py`) is a thin shim — it
resolves filenames via `file_manager`, reads its config, and calls the library
— so almost all logic lives in the testable package.

## License

GPL-3.0-or-later, matching Moonraker.
