import pytest

from conftest import gfile

from moonraker_contrast import api
from moonraker_contrast.errors import UnsupportedSlicerError


def test_scan_file(mappings):
    result = api.scan_file(gfile("prusa_footer.gcode"), mappings)
    assert result["slicer"] == "PrusaSlicer"
    assert result["raw"]["layer_height"] == 0.2
    assert result["canonical"]["elephant_foot_compensation"] == 0.2
    assert "prusa_only_setting" in result["passthrough"]


def test_compare_prusa_vs_orca_mostly_same(mappings):
    result = api.compare_files(
        gfile("prusa_footer.gcode"), gfile("orca_footer.gcode"), mappings
    )
    assert result["left"]["slicer"] == "PrusaSlicer"
    assert result["right"]["slicer"] == "OrcaSlicer"

    # Cross-slicer canonical keys should align as "same".
    for key in (
        "first_layer_height", "fill_density", "wall_count",
        "elephant_foot_compensation", "brim_separation",
        "top_solid_layers", "bottom_solid_layers", "spiral_vase",
        "supports_enabled",
    ):
        assert key in result["same_keys"], (
            f"{key} expected to match across slicers"
        )

    # Slicer-exclusive settings land in the only_* buckets.
    assert "prusa_only_setting" in result["only_left"]
    assert "orca_only_setting" in result["only_right"]


def test_compare_prusa_vs_bambu_reports_changed_layer_height(mappings):
    # Bambu fixture deliberately uses layer_height = 0.28 vs prusa 0.2.
    result = api.compare_files(
        gfile("prusa_footer.gcode"), gfile("bambu_header.gcode"), mappings
    )
    assert "layer_height" in result["changed"]
    assert result["changed"]["layer_height"]["left"]["value"] == 0.2
    assert result["changed"]["layer_height"]["right"]["value"] == 0.28
    # Inverted EFC still matches across slicers.
    assert "elephant_foot_compensation" in result["same_keys"]


def test_summary_counts_consistent(mappings):
    result = api.compare_files(
        gfile("prusa_footer.gcode"), gfile("orca_footer.gcode"), mappings
    )
    summary = result["summary"]
    assert summary["same"] == len(result["same_keys"])
    assert summary["changed"] == len(result["changed"])
    assert summary["only_left"] == len(result["only_left"])
    assert summary["only_right"] == len(result["only_right"])


def test_include_same_returns_values(mappings):
    result = api.compare_files(
        gfile("prusa_footer.gcode"), gfile("orca_footer.gcode"),
        mappings, include_same=True,
    )
    assert "same" in result
    assert "first_layer_height" in result["same"]
    assert result["same"]["first_layer_height"]["left"]["value"] == 0.2


def test_unsupported_slicer_raises(mappings):
    with pytest.raises(UnsupportedSlicerError):
        api.scan_file(gfile("cura_unsupported.gcode"), mappings)
