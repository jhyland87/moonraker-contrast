"""Parsers for BambuStudio / BambuSlicer (settings in the file header).

Unlike the PrusaSlicer family, BambuStudio writes no ``begin``/``end``
delimiters around its config -- it simply emits ``; key = value`` comment lines
in the header. So these parsers scan the whole header region (no markers).
"""

from .base import SlicerParser


class BambuStudioParser(SlicerParser):
    """Parser for BambuStudio: config lives unmarked in the file header."""

    config_location = "header"
    begin_marker = None  # no delimiters; scan the whole header
    end_marker = None


class BambuSlicerParser(BambuStudioParser):
    """Older BambuSlicer exports share BambuStudio's header convention."""
