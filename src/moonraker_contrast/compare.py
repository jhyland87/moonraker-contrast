"""Diff engine: bucket two normalized configs into same/changed/only_*.

Comparison happens over the union of canonical keys and passthrough keys. A
passthrough key only ever matches the *same* raw key on the other side -- we
make no cross-slicer equivalence claim for unmapped settings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .mapping import NormalizedConfig, _to_bool, _to_number


def values_equal(left_value: Any, right_value: Any, float_tolerance: float) -> bool:
    """Tolerant equality used to decide same vs changed.

    Order of checks:
      1. Both numeric (incl. numeric strings) -> compare within float_tolerance.
      2. Both bool-ish (0/1/true/false) -> compare as bool.
      3. Otherwise -> stripped string compare (no silent type coercion).
    """
    if left_value is None and right_value is None:
        return True
    if left_value is None or right_value is None:
        return False

    left_number = _to_number(left_value)
    right_number = _to_number(right_value)
    if left_number is not None and right_number is not None:
        return abs(left_number - right_number) <= float_tolerance

    left_bool = _to_bool(left_value)
    right_bool = _to_bool(right_value)
    if left_bool is not None and right_bool is not None:
        return left_bool == right_bool

    return str(left_value).strip() == str(right_value).strip()


def _entry(value: Any, raw_key: Optional[str]) -> Dict[str, Any]:
    return {"value": value, "raw_key": raw_key}


def _merged_view(config: NormalizedConfig) -> Dict[str, Tuple[Any, str, bool]]:
    """Flatten a NormalizedConfig to ``key -> (value, raw_key, is_canonical)``.

    Canonical keys take precedence; passthrough keys are added only when they
    don't collide with a canonical key name.
    """
    view: Dict[str, Tuple[Any, str, bool]] = {}
    for canonical_key, value in config.canonical.items():
        raw_key = config.provenance.get(canonical_key, canonical_key)
        view[canonical_key] = (value, raw_key, True)
    for raw_key, value in config.passthrough.items():
        if raw_key not in view:
            view[raw_key] = (value, raw_key, False)
    return view


def diff(
    left: NormalizedConfig,
    right: NormalizedConfig,
    float_tolerance: float,
) -> Dict[str, Any]:
    """Produce the diff buckets for two normalized configs.

    Returns a dict with ``changed``, ``only_left``, ``only_right`` (each
    ``key -> entry``) and ``same_keys`` (a sorted list of unchanged keys).
    """
    left_view = _merged_view(left)
    right_view = _merged_view(right)

    changed: Dict[str, Any] = {}
    only_left: Dict[str, Any] = {}
    only_right: Dict[str, Any] = {}
    same_keys: List[str] = []

    for key in sorted(set(left_view) | set(right_view)):
        in_left = key in left_view
        in_right = key in right_view
        if in_left and not in_right:
            left_value, left_raw_key, _ = left_view[key]
            only_left[key] = _entry(left_value, left_raw_key)
        elif in_right and not in_left:
            right_value, right_raw_key, _ = right_view[key]
            only_right[key] = _entry(right_value, right_raw_key)
        else:
            left_value, left_raw_key, left_is_canonical = left_view[key]
            right_value, right_raw_key, right_is_canonical = right_view[key]
            if values_equal(left_value, right_value, float_tolerance):
                same_keys.append(key)
            else:
                changed[key] = {
                    "left": _entry(left_value, left_raw_key),
                    "right": _entry(right_value, right_raw_key),
                    "canonical": left_is_canonical or right_is_canonical,
                }

    return {
        "changed": changed,
        "only_left": only_left,
        "only_right": only_right,
        "same_keys": same_keys,
    }
