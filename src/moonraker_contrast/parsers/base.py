"""Base slicer parser.

A parser knows where a slicer's config block lives (header vs footer) and how
the block is delimited, then turns it into a typed ``{key: value}`` dict. The
extraction/casting logic is shared (see :mod:`..extract`); subclasses only
declare their markers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..extract import parse_config_lines, select_region


@dataclass
class ParseResult:
    """Parsed settings plus a flag indicating the block may be incomplete."""

    settings: Dict[str, Any]
    #: True when the expected delimiters were not both found and we fell back
    #: to scanning the whole region (e.g. a footer truncated past READ_SIZE).
    partial: bool


class SlicerParser:
    """Base parser. Subclasses set the marker class attributes below."""

    #: "header" or "footer" -- which region to read. Usually mirrors
    #: ``SlicerInfo.config_location`` but kept here so a parser is self-describing.
    config_location: str = "footer"

    #: Regexes (as strings) that bound the config block within the region.
    #: When both are None the entire region is scanned (BambuStudio style).
    begin_marker: Optional[str] = None
    end_marker: Optional[str] = None

    #: Keys we never want in a settings diff (binary blobs / per-print noise).
    ignore_keys = {
        "thumbnail", "thumbnail_QOI", "thumbnail_PNG", "thumbnail_JPG",
    }

    def __init__(self, slicer_info) -> None:
        self.slicer_info = slicer_info
        self._begin_regex = (
            re.compile(self.begin_marker) if self.begin_marker else None
        )
        self._end_regex = (
            re.compile(self.end_marker) if self.end_marker else None
        )

    def parse(self, header: str, footer: str) -> ParseResult:
        """Extract the config block and parse it into typed settings."""
        region = select_region(header, footer, self.config_location)
        block_text, is_partial = self._slice_block(region)
        settings = parse_config_lines(block_text, ignore_keys=self.ignore_keys)
        return ParseResult(settings=settings, partial=is_partial)

    def _slice_block(self, region: str):
        """Return ``(block_text, is_partial)`` for the delimited config block.

        If no markers are configured, the whole region is the block. If markers
        are configured but not both found, we fall back to the whole region and
        flag ``is_partial=True`` so callers can warn the user.
        """
        if self._begin_regex is None and self._end_regex is None:
            return region, False

        begin_match = self._begin_regex.search(region) if self._begin_regex else None
        end_match = self._end_regex.search(region) if self._end_regex else None

        if (
            begin_match is not None
            and end_match is not None
            and end_match.start() > begin_match.end()
        ):
            return region[begin_match.end():end_match.start()], False

        # Markers expected but not cleanly found -> best-effort whole region.
        return region, True


# Re-export for the registry module's convenience.
__all__: List[str] = ["SlicerParser", "ParseResult"]
