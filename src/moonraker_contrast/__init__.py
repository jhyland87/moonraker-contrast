"""moonraker_contrast -- compare slicer settings embedded in two gcode files.

Pure-stdlib library. The Moonraker component shim (installed separately into
``moonraker/components/``) imports :mod:`moonraker_contrast.api`.
"""

from __future__ import annotations

from .api import MappingStore, compare_files, load_mappings, scan_file
from .errors import (
    ConfigBlockNotFoundError,
    ContrastError,
    MappingLoadError,
    UnsupportedSlicerError,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "compare_files",
    "scan_file",
    "load_mappings",
    "MappingStore",
    "ContrastError",
    "UnsupportedSlicerError",
    "ConfigBlockNotFoundError",
    "MappingLoadError",
]
