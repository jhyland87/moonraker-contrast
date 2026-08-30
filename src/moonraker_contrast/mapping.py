"""User-editable cross-slicer setting mappings + value normalization.

The mapping file is INI (configparser) -- the same format as ``moonraker.conf``
-- so it is hand-editable and works in Mainsail/Fluidd config editors.

Schema
------
``[canonical <name>]`` sections declare one logical setting and how each slicer
names it, with an optional value transform applied toward canonical space::

    [canonical elephant_foot_compensation]
    prusaslicer = elefant_foot_compensation
    orcaslicer  = elefant_foot_compensation
    bambustudio = xy_contour_compensation | invert_number

A ``[settings]`` section holds globals (currently ``float_tolerance``).

Transforms are named and invertible. Unknown transforms are logged and the
offending line is skipped (fail-soft) so one bad entry can't break the file.
"""

from __future__ import annotations

import configparser
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .errors import MappingLoadError

logger = logging.getLogger(__name__)

Transform = Callable[[Any], Any]


# --------------------------------------------------------------------------- #
# Value coercion helpers
# --------------------------------------------------------------------------- #
def _to_number(value: Any) -> Optional[float]:
    """Best-effort numeric coercion; returns None if not numeric."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().rstrip("%").strip()
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


_TRUE_TOKENS = {"1", "true", "yes", "on"}
_FALSE_TOKENS = {"0", "false", "no", "off", ""}


def _to_bool(value: Any) -> Optional[bool]:
    """Coerce slicer truthy/falsy encodings to bool; None if ambiguous."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    return None


def _preserve_int(number: float) -> Any:
    """Return an int when the float is whole, else the float (tidier output)."""
    return int(number) if number == int(number) else number


# --------------------------------------------------------------------------- #
# Transform registry
# --------------------------------------------------------------------------- #
def _transform_identity(value: Any) -> Any:
    return value


def _transform_invert_number(value: Any) -> Any:
    number = _to_number(value)
    return value if number is None else _preserve_int(-number)


def _transform_invert_bool(value: Any) -> Any:
    boolean = _to_bool(value)
    return value if boolean is None else (not boolean)


def _transform_as_bool(value: Any) -> Any:
    boolean = _to_bool(value)
    return value if boolean is None else boolean


def _transform_percent_to_float(value: Any) -> Any:
    number = _to_number(value)
    return value if number is None else number / 100.0


def _transform_float_to_percent(value: Any) -> Any:
    number = _to_number(value)
    return value if number is None else f"{_preserve_int(number * 100.0)}%"


#: Transforms with no argument.
_SIMPLE_TRANSFORMS: Dict[str, Transform] = {
    "identity": _transform_identity,
    "invert_number": _transform_invert_number,
    "invert_bool": _transform_invert_bool,
    "as_bool": _transform_as_bool,
    "percent_to_float": _transform_percent_to_float,
    "float_to_percent": _transform_float_to_percent,
}


def _make_scale_transform(factor: float) -> Transform:
    def _scale(value: Any) -> Any:
        number = _to_number(value)
        return value if number is None else _preserve_int(number * factor)

    return _scale


def parse_transform(transform_spec: str) -> Transform:
    """Parse a transform spec like ``invert_number`` or ``scale:25.4``.

    Raises ``ValueError`` for unknown names so the loader can skip the line.
    """
    transform_spec = transform_spec.strip()
    if not transform_spec or transform_spec == "identity":
        return _transform_identity
    if transform_spec in _SIMPLE_TRANSFORMS:
        return _SIMPLE_TRANSFORMS[transform_spec]
    if transform_spec.startswith("scale:"):
        try:
            return _make_scale_transform(float(transform_spec.split(":", 1)[1]))
        except (ValueError, IndexError) as exc:
            raise ValueError(
                f"invalid scale transform: {transform_spec!r}"
            ) from exc
    raise ValueError(f"unknown transform: {transform_spec!r}")


# --------------------------------------------------------------------------- #
# Mappings + Normalizer
# --------------------------------------------------------------------------- #
@dataclass
class NormalizedConfig:
    """Result of normalizing one file's raw settings to canonical space."""

    #: canonical_key -> transformed value (comparable across slicers).
    canonical: Dict[str, Any]
    #: raw_key -> value, for settings with no mapping (compared as-is).
    passthrough: Dict[str, Any]
    #: canonical_key -> the raw slicer key it came from (for output).
    provenance: Dict[str, str]


@dataclass
class Mappings:
    """Loaded mapping table + globals."""

    #: slicer_name(lower) -> { raw_key -> (canonical_key, transform) }
    by_slicer: Dict[str, Dict[str, Tuple[str, Transform]]] = field(default_factory=dict)
    float_tolerance: float = 1e-6

    def normalize(
        self, raw_settings: Dict[str, Any], slicer_name: str
    ) -> NormalizedConfig:
        """Map one file's raw settings into canonical + passthrough buckets."""
        raw_key_index = self.by_slicer.get(slicer_name.lower(), {})
        canonical: Dict[str, Any] = {}
        passthrough: Dict[str, Any] = {}
        provenance: Dict[str, str] = {}
        for raw_key, value in raw_settings.items():
            mapping_entry = raw_key_index.get(raw_key)
            if mapping_entry is None:
                passthrough[raw_key] = value
            else:
                canonical_key, transform = mapping_entry
                canonical[canonical_key] = transform(value)
                provenance[canonical_key] = raw_key
        return NormalizedConfig(canonical, passthrough, provenance)


_CANONICAL_SECTION_PREFIX = "canonical "


def load_mappings(mapping_path: str) -> Mappings:
    """Load and parse the INI mapping file.

    Raises ``MappingLoadError`` only on wholesale failure (missing/garbled
    file). Individual bad option lines are logged and skipped.
    """
    mapping_file = Path(os.path.expanduser(str(mapping_path)))
    if not mapping_file.is_file():
        raise MappingLoadError(f"mapping file not found: {mapping_file}")

    config_parser = configparser.ConfigParser(interpolation=None)
    try:
        with open(mapping_file, "r", encoding="utf-8") as file_handle:
            config_parser.read_file(file_handle)
    except (OSError, configparser.Error) as exc:
        raise MappingLoadError(
            f"could not parse mapping file {mapping_file}: {exc}"
        ) from exc

    mappings = Mappings()

    if config_parser.has_section("settings"):
        try:
            mappings.float_tolerance = config_parser.getfloat(
                "settings", "float_tolerance", fallback=1e-6
            )
        except ValueError:
            logger.warning(
                "invalid float_tolerance in %s; using 1e-6", mapping_file
            )

    for section_name in config_parser.sections():
        if not section_name.lower().startswith(_CANONICAL_SECTION_PREFIX):
            continue
        canonical_key = section_name[len(_CANONICAL_SECTION_PREFIX):].strip()
        if not canonical_key:
            logger.warning(
                "skipping canonical section with empty name in %s", mapping_file
            )
            continue
        for slicer_name, raw_spec in config_parser.items(section_name):
            raw_key, _, transform_spec = raw_spec.partition("|")
            raw_key = raw_key.strip()
            if not raw_key:
                logger.warning(
                    "skipping empty raw key for %s/%s in %s",
                    canonical_key, slicer_name, mapping_file,
                )
                continue
            try:
                transform = (
                    parse_transform(transform_spec)
                    if transform_spec.strip()
                    else _transform_identity
                )
            except ValueError as exc:
                logger.warning(
                    "skipping %s/%s in %s: %s",
                    canonical_key, slicer_name, mapping_file, exc,
                )
                continue
            mappings.by_slicer.setdefault(slicer_name.lower(), {})[raw_key] = (
                canonical_key,
                transform,
            )

    return mappings


class MappingStore:
    """Caches a Mappings object and hot-reloads it when the file's mtime changes.

    Used by the component shim so editing ``slicer_mappings.cfg`` takes effect
    without restarting Moonraker.
    """

    def __init__(self, mapping_path: str) -> None:
        self.mapping_path = os.path.expanduser(str(mapping_path))
        self._last_mtime: Optional[float] = None
        self._cached_mappings: Optional[Mappings] = None

    def get(self) -> Mappings:
        """Return the mappings, reloading from disk if the file changed."""
        try:
            current_mtime = os.path.getmtime(self.mapping_path)
        except OSError:
            current_mtime = None
        if self._cached_mappings is None or current_mtime != self._last_mtime:
            self._cached_mappings = load_mappings(self.mapping_path)
            self._last_mtime = current_mtime
        return self._cached_mappings
