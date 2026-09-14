"""Library facade for the config-file compare resource.

Mirrors :mod:`api`'s shape (nothing here imports Moonraker) but for whole
Klipper/Moonraker config files (``printer.cfg``, ``moonraker.conf``, etc.)
instead of slicer settings embedded in gcode.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .config_diff import diff_raw, diff_values
from .config_parse import parse_config_file

__all__ = ["compare_config_files", "scan_config_file"]

DEFAULT_FLOAT_TOLERANCE = 1e-6


def scan_config_file(path: Path, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Parse a single config file. Useful for debugging / future UI."""
    path = Path(path)
    display_name = display_name or path.name
    values = parse_config_file(path)
    sections = {key.rsplit(".", 1)[0] for key in values}
    return {
        "file": display_name,
        "sections": len(sections),
        "options": len(values),
        "values": values,
    }


def compare_config_files(
    left_path: Path,
    right_path: Path,
    *,
    mode: str = "values",
    float_tolerance: float = DEFAULT_FLOAT_TOLERANCE,
    left_name: Optional[str] = None,
    right_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare two config files and return either a raw or values diff.

    ``mode="raw"`` returns a literal unified text diff; ``mode="values"``
    (default) returns a semantic diff of parsed settings -- files that differ
    only in comments, whitespace, or section ordering report no differences.
    """
    left_path, right_path = Path(left_path), Path(right_path)
    left_name = left_name or left_path.name
    right_name = right_name or right_path.name

    response: Dict[str, Any] = {
        "left": {"file": left_name},
        "right": {"file": right_name},
        "mode": mode,
    }

    if mode == "raw":
        left_text = left_path.read_text(encoding="utf-8", errors="ignore")
        right_text = right_path.read_text(encoding="utf-8", errors="ignore")
        response["raw"] = diff_raw(left_text, right_text, left_name, right_name)
        return response

    left_values = parse_config_file(left_path)
    right_values = parse_config_file(right_path)
    response["left"]["sections"] = len({key.rsplit(".", 1)[0] for key in left_values})
    response["left"]["options"] = len(left_values)
    response["right"]["sections"] = len({key.rsplit(".", 1)[0] for key in right_values})
    response["right"]["options"] = len(right_values)

    diff_buckets = diff_values(left_values, right_values, float_tolerance)
    response["summary"] = {
        "same": len(diff_buckets["same_keys"]),
        "changed": len(diff_buckets["changed"]),
        "only_left": len(diff_buckets["only_left"]),
        "only_right": len(diff_buckets["only_right"]),
    }
    response.update(diff_buckets)
    return response
