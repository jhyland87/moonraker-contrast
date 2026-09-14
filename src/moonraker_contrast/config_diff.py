"""Diff engines for the config-file compare resource.

Two independent modes:
  * :func:`diff_values` -- semantic diff over parsed ``"section.option" -> value``
    dicts (see :mod:`config_parse`). Reuses :func:`compare.values_equal` for the
    same tolerant numeric/bool/string equality the gcode compare resource uses.
  * :func:`diff_text` -- literal line-by-line diff (comments, whitespace,
    ordering all count) via the stdlib ``difflib`` (this project is stdlib-only
    by design), returned as structured JSON hunks rather than a preformatted
    unified-diff text blob.

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


#: Context lines kept around each change, same default as difflib.unified_diff.
_CONTEXT_LINES = 3


def _hunk_lines(
    tag: str, left_lines: List[str], right_lines: List[str],
    i1: int, i2: int, j1: int, j2: int,
) -> List[Dict[str, Any]]:
    """Expand one difflib opcode into per-line JSON entries for a hunk."""
    lines: List[Dict[str, Any]] = []
    if tag == "equal":
        for offset, text in enumerate(left_lines[i1:i2]):
            lines.append({
                "type": "context",
                "left_line": i1 + offset + 1,
                "right_line": j1 + offset + 1,
                "text": text,
            })
        return lines
    if tag in ("replace", "delete"):
        for offset, text in enumerate(left_lines[i1:i2]):
            lines.append({
                "type": "remove",
                "left_line": i1 + offset + 1,
                "right_line": None,
                "text": text,
            })
    if tag in ("replace", "insert"):
        for offset, text in enumerate(right_lines[j1:j2]):
            lines.append({
                "type": "add",
                "left_line": None,
                "right_line": j1 + offset + 1,
                "text": text,
            })
    return lines


def diff_text(left_text: str, right_text: str) -> Dict[str, Any]:
    """Structured line-by-line diff -- no value parsing, just literal text.

    Returns JSON hunks (grouped changes with surrounding context, like a
    unified diff) instead of a preformatted diff string, so callers don't have
    to parse diff-format text out of a JSON response.
    """
    left_lines = left_text.splitlines()
    right_lines = right_text.splitlines()
    matcher = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)

    lines_added = 0
    lines_removed = 0
    hunks: List[Dict[str, Any]] = []
    for group in matcher.get_grouped_opcodes(_CONTEXT_LINES):
        hunk_lines: List[Dict[str, Any]] = []
        for tag, i1, i2, j1, j2 in group:
            hunk_lines.extend(_hunk_lines(tag, left_lines, right_lines, i1, i2, j1, j2))
            if tag in ("replace", "delete"):
                lines_removed += i2 - i1
            if tag in ("replace", "insert"):
                lines_added += j2 - j1
        hunks.append({
            "left_start": group[0][1] + 1,
            "left_lines": group[-1][2] - group[0][1],
            "right_start": group[0][3] + 1,
            "right_lines": group[-1][4] - group[0][3],
            "lines": hunk_lines,
        })

    return {
        "identical": not hunks,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "hunks": hunks,
    }
