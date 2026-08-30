"""Library facade -- the surface the Moonraker component shim calls.

Nothing here imports Moonraker, so the whole library is unit-testable without a
printer. The shim resolves filenames to paths and translates exceptions; this
module does the parse -> normalize -> diff pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .compare import _merged_view, diff
from .detect import SlicerInfo, detect_slicer, read_regions
from .errors import UnsupportedSlicerError
from .mapping import Mappings, NormalizedConfig, MappingStore, load_mappings
from .parsers import ParseResult, get_parser_for

__all__ = [
    "compare_files",
    "scan_file",
    "load_mappings",
    "MappingStore",
]


def _analyze(path: Path) -> Tuple[SlicerInfo, ParseResult]:
    """Detect the slicer and parse its config block. Reads the file once."""
    path = Path(path)
    header, footer = read_regions(path)
    slicer_info = detect_slicer(header, footer)
    if slicer_info is None:
        raise UnsupportedSlicerError(
            f"could not identify a supported slicer for {path.name!r} "
            f"(Cura and files without an embedded config block are not supported)"
        )
    parser = get_parser_for(slicer_info)
    parse_result = parser.parse(header, footer)
    return slicer_info, parse_result


def _file_meta(
    display_name: str, slicer_info: SlicerInfo, parse_result: ParseResult
) -> Dict[str, Any]:
    return {
        "file": display_name,
        "slicer": slicer_info.name,
        "version": slicer_info.version,
        "partial": parse_result.partial,
    }


def scan_file(
    path: Path,
    mappings: Mappings,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse and normalize a single file's slicer settings.

    Useful for debugging / future UI: shows the raw values, the canonical
    (cross-slicer) view, and which raw keys had no mapping.
    """
    path = Path(path)
    display_name = display_name or path.name
    slicer_info, parse_result = _analyze(path)
    normalized = mappings.normalize(parse_result.settings, slicer_info.name)
    return {
        **_file_meta(display_name, slicer_info, parse_result),
        "raw": parse_result.settings,
        "canonical": normalized.canonical,
        "provenance": normalized.provenance,
        "passthrough": normalized.passthrough,
    }


def compare_files(
    left_path: Path,
    right_path: Path,
    mappings: Mappings,
    *,
    float_tolerance: Optional[float] = None,
    include_same: bool = False,
    left_name: Optional[str] = None,
    right_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare two gcode files' slicer settings and return the diff schema."""
    left_path, right_path = Path(left_path), Path(right_path)
    left_name = left_name or left_path.name
    right_name = right_name or right_path.name
    if float_tolerance is None:
        float_tolerance = mappings.float_tolerance

    left_info, left_result = _analyze(left_path)
    right_info, right_result = _analyze(right_path)

    left_normalized = mappings.normalize(left_result.settings, left_info.name)
    right_normalized = mappings.normalize(right_result.settings, right_info.name)

    diff_buckets = diff(left_normalized, right_normalized, float_tolerance)

    warnings = []
    if left_result.partial:
        warnings.append(f"{left_name}: config block may be incomplete (truncated)")
    if right_result.partial:
        warnings.append(f"{right_name}: config block may be incomplete (truncated)")

    response: Dict[str, Any] = {
        "left": _file_meta(left_name, left_info, left_result),
        "right": _file_meta(right_name, right_info, right_result),
        "summary": {
            "same": len(diff_buckets["same_keys"]),
            "changed": len(diff_buckets["changed"]),
            "only_left": len(diff_buckets["only_left"]),
            "only_right": len(diff_buckets["only_right"]),
        },
        "changed": diff_buckets["changed"],
        "only_left": diff_buckets["only_left"],
        "only_right": diff_buckets["only_right"],
        "same_keys": diff_buckets["same_keys"],
        "warnings": warnings,
    }

    if include_same:
        response["same"] = _same_values(
            left_normalized, right_normalized, diff_buckets["same_keys"]
        )

    return response


def _same_values(
    left: NormalizedConfig,
    right: NormalizedConfig,
    same_keys,
) -> Dict[str, Any]:
    """Build full left/right values for the unchanged keys (include_same=true)."""
    left_view = _merged_view(left)
    right_view = _merged_view(right)
    same: Dict[str, Any] = {}
    for key in same_keys:
        left_value, left_raw_key, is_canonical = left_view[key]
        right_value, right_raw_key, _ = right_view[key]
        same[key] = {
            "left": {"value": left_value, "raw_key": left_raw_key},
            "right": {"value": right_value, "raw_key": right_raw_key},
            "canonical": is_canonical,
        }
    return same
