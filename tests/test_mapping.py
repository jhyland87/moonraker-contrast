import textwrap

import pytest

from moonraker_contrast.errors import MappingLoadError
from moonraker_contrast.mapping import (
    Mappings,
    load_mappings,
    parse_transform,
)


def test_default_mapping_loads(mappings):
    assert isinstance(mappings, Mappings)
    # prusaslicer should know elefant_foot_compensation maps to a canonical key.
    prusa_index = mappings.by_slicer["prusaslicer"]
    canonical_key, _ = prusa_index["elefant_foot_compensation"]
    assert canonical_key == "elephant_foot_compensation"


def test_invert_number_transform():
    transform = parse_transform("invert_number")
    assert transform(-0.2) == 0.2
    assert transform(0.2) == -0.2
    assert transform("PLA") == "PLA"          # non-numeric passes through


def test_percent_to_float_transform():
    transform = parse_transform("percent_to_float")
    assert transform("75%") == 0.75
    assert transform(50) == 0.5


def test_as_bool_transform():
    transform = parse_transform("as_bool")
    assert transform(1) is True
    assert transform("true") is True
    assert transform(0) is False
    assert transform("0") is False


def test_scale_transform():
    transform = parse_transform("scale:25.4")
    assert transform(1) == 25.4


def test_unknown_transform_raises():
    with pytest.raises(ValueError):
        parse_transform("frobnicate")


def test_bambu_efc_inverts_into_canonical(mappings):
    # BambuStudio stores xy_contour_compensation; normalized EFC should flip sign.
    normalized = mappings.normalize({"xy_contour_compensation": -0.2}, "BambuStudio")
    assert normalized.canonical["elephant_foot_compensation"] == 0.2
    assert (
        normalized.provenance["elephant_foot_compensation"]
        == "xy_contour_compensation"
    )


def test_unmapped_keys_passthrough(mappings):
    normalized = mappings.normalize({"some_weird_key": 5}, "PrusaSlicer")
    assert normalized.passthrough == {"some_weird_key": 5}
    assert "some_weird_key" not in normalized.canonical


def test_bad_line_is_skipped_not_fatal(tmp_path):
    mapping_file = tmp_path / "m.cfg"
    mapping_file.write_text(textwrap.dedent("""
        [canonical foo]
        prusaslicer = good_key
        orcaslicer = bad_key | frobnicate

        [canonical bar]
        prusaslicer = bar_key
    """))
    mappings = load_mappings(str(mapping_file))
    # good_key survived; the frobnicate line was dropped; bar still loaded.
    assert mappings.by_slicer["prusaslicer"]["good_key"][0] == "foo"
    assert "bad_key" not in mappings.by_slicer.get("orcaslicer", {})
    assert mappings.by_slicer["prusaslicer"]["bar_key"][0] == "bar"


def test_missing_file_raises():
    with pytest.raises(MappingLoadError):
        load_mappings("/nonexistent/path/to/mappings.cfg")
