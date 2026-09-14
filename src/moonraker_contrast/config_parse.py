"""Parsing for Klipper/Moonraker-style config files (``printer.cfg``, etc.).

Unlike the gcode/slicer pipeline (:mod:`detect`, :mod:`parsers`, :mod:`extract`),
these files are already well-formed INI -- the same format :mod:`mapping` already
reads for the mapping file -- so we go straight to :mod:`configparser` instead of
hand-rolled regex extraction.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any, Dict

from .errors import ConfigParseError
from .extract import cast_value


def parse_config_file(path: Path) -> Dict[str, Any]:
    """Parse a config file into a flat ``"section.option" -> value`` dict.

    Uses ``interpolation=None`` (values commonly contain literal ``%``, e.g. speed
    percentages) and ``strict=False`` (real Klipper files can have bare, repeated
    ``[include ...]`` section headers). Values are cast via
    :func:`extract.cast_value` so numeric settings compare with tolerance later.

    Klipper's auto-generated ``#*# <SAVE_CONFIG>`` block uses ``#*#``-prefixed
    lines, which ``configparser``'s default comment prefixes already treat as
    comments -- so that block is transparently excluded here.
    """
    path = Path(path)
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as file_handle:
            parser.read_file(file_handle)
    except (OSError, configparser.Error) as exc:
        raise ConfigParseError(f"could not parse config file {path}: {exc}") from exc

    values: Dict[str, Any] = {}
    for section_name in parser.sections():
        for option, raw_value in parser.items(section_name):
            values[f"{section_name}.{option}"] = cast_value(raw_value)
    return values
