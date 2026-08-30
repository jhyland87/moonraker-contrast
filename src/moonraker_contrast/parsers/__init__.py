"""Parser registry: map a detected slicer to its parser.

Selection is by ``SlicerInfo.name`` with a per-family fallback, so an
unrecognized-but-related fork (e.g. a niche slic3r derivative reported via the
legacy fallback regex) still gets a sensible parser.
"""

from __future__ import annotations

from typing import Dict, Type

from ..detect import SlicerInfo
from .base import ParseResult, SlicerParser
from .bambu import BambuSlicerParser, BambuStudioParser
from .prusa import OrcaSlicerParser, PrusaSlicerParser, SuperSlicerParser

#: Exact-name -> parser class.
PARSER_REGISTRY: Dict[str, Type[SlicerParser]] = {
    "PrusaSlicer": PrusaSlicerParser,
    "SuperSlicer": SuperSlicerParser,
    "OrcaSlicer": OrcaSlicerParser,
    "BambuStudio": BambuStudioParser,
    "BambuSlicer": BambuSlicerParser,
}

#: Family -> default parser when the exact name is unknown.
_FAMILY_DEFAULT: Dict[str, Type[SlicerParser]] = {
    "prusa": PrusaSlicerParser,
    "bambu": BambuStudioParser,
}


def get_parser_for(slicer_info: SlicerInfo) -> SlicerParser:
    """Return an instantiated parser for the detected slicer."""
    parser_class = (
        PARSER_REGISTRY.get(slicer_info.name)
        or _FAMILY_DEFAULT.get(slicer_info.family)
    )
    if parser_class is None:
        # Detection only ever yields known families, but guard anyway.
        parser_class = PrusaSlicerParser
    return parser_class(slicer_info)


__all__ = [
    "PARSER_REGISTRY",
    "ParseResult",
    "SlicerParser",
    "get_parser_for",
    "PrusaSlicerParser",
    "SuperSlicerParser",
    "OrcaSlicerParser",
    "BambuStudioParser",
    "BambuSlicerParser",
]
