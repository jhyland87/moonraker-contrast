"""Diff engines for the config-file compare resource.

Two independent modes:
  * :func:`diff_values` -- semantic diff over parsed ``"section.option" -> value``
    dicts (see :mod:`config_parse`). Reuses :func:`compare.values_equal` for the
    same tolerant numeric/bool/string equality the gcode compare resource uses.
  * :func:`diff_raw` -- literal text diff (comments, whitespace, ordering all
    count), via the stdlib ``difflib`` (this project is stdlib-only by design).

Unlike :func:`compare.diff`, there's no canonical/raw_key concept here -- config
keys are compared directly against the same key on the other side, so the bucket
entries are plain values rather than ``{value, raw_key}`` wrappers.
"""

from __future__ import annotations

import difflib
from typing import Any, Dict, List

from .compare import values_equal


def diff_values(
    left: Dict[str, Any],
    right: Dict[str, Any],
    float_tolerance: float,
) -> Dict[str, Any]:
    """Bucket two flattened config dicts into changed/only_left/only_right/same_keys."""
    changed: Dict[str, Any] = {}
    only_left: Dict[str, Any] = {}
    only_right: Dict[str, Any] = {}
    same_keys: List[str] = []

    for key in sorted(set(left) | set(right)):
        in_left = key in left
        in_right = key in right
        if in_left and not in_right:
            only_left[key] = left[key]
        elif in_right and not in_left:
            only_right[key] = right[key]
        elif values_equal(left[key], right[key], float_tolerance):
            same_keys.append(key)
        else:
            changed[key] = {"left": left[key], "right": right[key]}

    return {
        "changed": changed,
        "only_left": only_left,
        "only_right": only_right,
        "same_keys": same_keys,
    }


def diff_raw(
    left_text: str, right_text: str, left_name: str, right_name: str
) -> Dict[str, Any]:
    """Literal unified-diff of two files' text."""
    left_lines = left_text.splitlines(keepends=True)
    right_lines = right_text.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            left_lines, right_lines, fromfile=left_name, tofile=right_name
        )
    )
    lines_added = sum(
        1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
    )
    lines_removed = sum(
        1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
    )
    return {
        "identical": not diff_lines,
        "diff": "".join(diff_lines),
        "lines_added": lines_added,
        "lines_removed": lines_removed,
    }
