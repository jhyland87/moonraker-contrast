"""Typed exceptions for moonraker_contrast.

The component shim translates these into Moonraker ``server.error`` responses
with appropriate HTTP status codes, but the library itself never imports
Moonraker, so it raises plain exceptions instead.
"""

from __future__ import annotations


class ContrastError(Exception):
    """Base class for all moonraker_contrast errors."""

    #: Suggested HTTP status code when surfaced through the API.
    http_status: int = 400


class UnsupportedSlicerError(ContrastError):
    """Raised when a gcode file was produced by a slicer we cannot parse.

    This includes Cura (which does not embed its full settings by default)
    and any file with no recognizable slicer marker.
    """

    http_status = 400


class ConfigBlockNotFoundError(ContrastError):
    """Raised when the slicer is identified but no settings block can be read."""

    http_status = 422


class MappingLoadError(ContrastError):
    """Raised when the mapping file cannot be read or parsed at all.

    Individual bad lines inside an otherwise-valid mapping file are skipped
    (fail-soft); this is only raised for a wholesale failure (missing/garbled
    file) so the caller can decide whether to proceed with an empty mapping.
    """

    http_status = 500
