"""Config-block extraction helpers shared by all parsers.

The heavy lifting of reading file regions lives in :mod:`detect` (``read_regions``)
so a file is read exactly once. This module turns a region of text into a typed
``{key: value}`` dict.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

#: ``; key = value`` config line as written by the slic3r/Bambu engines.
#: Keys are restricted to identifier characters; values are taken verbatim
#: (trailing whitespace trimmed) so transforms can interpret them later.
CONFIG_LINE_RE = re.compile(r"^;\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")

#: A pure integer or float (optionally signed), used by ``cast_value``.
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")


def select_region(header: str, footer: str, location: str) -> str:
    """Return the region of text that holds the config block."""
    return header if location == "header" else footer


def cast_value(raw: str) -> Any:
    """Convert a raw config value string to a typed Python value.

    Intentionally conservative:
      * Ints stay ints, floats stay floats. We do NOT coerce ``0``/``1`` to
        bool here -- many numeric settings legitimately use 0/1, so booleanness
        is decided later at the transform/compare layer (via ``as_bool``).
      * Percent strings ("75%") are kept as strings; percent<->float semantics
        belong to declared transforms, not to eager casting.
      * Comma lists are kept as the raw string unless a caller explicitly opts
        in to splitting, to avoid noisy diffs from multi-extruder reorderings.
      * Empty string -> None.
    """
    if raw == "":
        return None
    if _INT_RE.match(raw):
        try:
            return int(raw)
        except ValueError:
            return raw
    if _FLOAT_RE.match(raw):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def parse_config_lines(
    region: str,
    ignore_keys: Optional[set] = None,
) -> Dict[str, Any]:
    """Parse every ``; key = value`` line in ``region`` into a typed dict.

    Later occurrences of a key win (slicers occasionally repeat keys; the last
    one written is authoritative). Keys in ``ignore_keys`` are skipped.
    """
    ignore_keys = ignore_keys or set()
    settings: Dict[str, Any] = {}
    for line in region.splitlines():
        if not line.startswith(";"):
            continue
        line_match = CONFIG_LINE_RE.match(line)
        if line_match is None:
            continue
        key = line_match.group(1)
        if key in ignore_keys:
            continue
        settings[key] = cast_value(line_match.group(2))
    return settings
