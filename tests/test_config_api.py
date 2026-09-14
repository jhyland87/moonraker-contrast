import pytest

from conftest import gfile

from moonraker_contrast import config_api
from moonraker_contrast.errors import ConfigParseError


def test_scan_config_file():
    result = config_api.scan_config_file(gfile("config_a.cfg"))
    assert result["file"] == "config_a.cfg"
    assert result["values"]["extruder.pressure_advance"] == 0.04
    assert result["options"] == len(result["values"])


def test_compare_values_mode_detects_real_changes():
    result = config_api.compare_config_files(
        gfile("config_a.cfg"), gfile("config_b.cfg"), mode="values",
    )
    assert result["mode"] == "values"
    assert result["changed"]["extruder.pressure_advance"] == {
        "left": 0.04, "right": 0.06,
    }
    assert "old_only_section.some_option" in result["only_left"]
    assert "new_only_section.some_option" in result["only_right"]
    # SAVE_CONFIG calibration differences must not leak into the values diff.
    assert not any("stepper_z default" in key for key in result["changed"])


def test_compare_values_mode_summary_counts_consistent():
    result = config_api.compare_config_files(
        gfile("config_a.cfg"), gfile("config_b.cfg"), mode="values",
    )
    summary = result["summary"]
    assert summary["same"] == len(result["same_keys"])
    assert summary["changed"] == len(result["changed"])
    assert summary["only_left"] == len(result["only_left"])
    assert summary["only_right"] == len(result["only_right"])


def test_reformatted_file_reports_no_values_diff():
    result = config_api.compare_config_files(
        gfile("config_a.cfg"), gfile("config_a_reformatted.cfg"), mode="values",
    )
    assert result["changed"] == {}
    assert result["only_left"] == {}
    assert result["only_right"] == {}


def test_reformatted_file_reports_raw_diff():
    result = config_api.compare_config_files(
        gfile("config_a.cfg"), gfile("config_a_reformatted.cfg"), mode="raw",
    )
    assert result["mode"] == "raw"
    assert result["raw"]["identical"] is False
    assert result["raw"]["lines_added"] > 0
    assert result["raw"]["lines_removed"] > 0


def test_identical_file_raw_diff_reports_identical():
    result = config_api.compare_config_files(
        gfile("config_a.cfg"), gfile("config_a.cfg"), mode="raw",
    )
    assert result["raw"]["identical"] is True


def test_garbled_file_raises_in_values_mode_but_not_raw_mode():
    with pytest.raises(ConfigParseError):
        config_api.compare_config_files(
            gfile("config_a.cfg"), gfile("config_garbled.cfg"), mode="values",
        )
    # Raw mode never parses INI, so a garbled file is still comparable as text.
    result = config_api.compare_config_files(
        gfile("config_a.cfg"), gfile("config_garbled.cfg"), mode="raw",
    )
    assert result["raw"]["identical"] is False
