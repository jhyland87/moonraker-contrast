"""Parsers for the PrusaSlicer family (settings in the file footer).

PrusaSlicer and SuperSlicer wrap their config in
``; prusaslicer_config = begin`` / ``; prusaslicer_config = end`` (SuperSlicer
historically kept the ``prusaslicer_config`` token). OrcaSlicer descends from
the same engine but emits ``; CONFIG_BLOCK_START`` / ``; CONFIG_BLOCK_END``.

All three write settings as ``; key = value`` comment lines.
"""

from .base import SlicerParser


class PrusaSlicerParser(SlicerParser):
    """Parser for PrusaSlicer: config in the footer between ``*_config`` markers."""

    config_location = "footer"
    # Loosened to accept prusaslicer_config / slic3r_config / <fork>_config.
    begin_marker = r";\s*[A-Za-z0-9_]*config\s*=\s*begin"
    end_marker = r";\s*[A-Za-z0-9_]*config\s*=\s*end"


class SuperSlicerParser(PrusaSlicerParser):
    """SuperSlicer uses the same footer/marker convention as PrusaSlicer."""


class OrcaSlicerParser(PrusaSlicerParser):
    """OrcaSlicer: footer config, but with CONFIG_BLOCK_START/END delimiters."""

    begin_marker = r";\s*CONFIG_BLOCK_START"
    end_marker = r";\s*CONFIG_BLOCK_END"
