import pytest

from conftest import gfile

from moonraker_contrast.config_parse import parse_config_file
from moonraker_contrast.errors import ConfigParseError


def test_flattens_sections_to_dotted_keys():
    values = parse_config_file(gfile("config_a.cfg"))
    assert values["mcu.serial"] == "/dev/ttyS7"
    assert values["extruder.pressure_advance"] == 0.04
    assert values["stepper_z.position_endstop"] == 0.015


def test_casts_numeric_values():
    values = parse_config_file(gfile("config_a.cfg"))
    assert values["mcu.baud"] == 230400
    assert isinstance(values["mcu.baud"], int)
    assert values["extruder.pressure_advance"] == 0.04
    assert isinstance(values["extruder.pressure_advance"], float)


def test_save_config_block_excluded():
    values = parse_config_file(gfile("config_a.cfg"))
    assert not any(key.startswith("bed_mesh default") for key in values)
    assert "stepper_z.position_endstop" in values
    # Only the real (non-#*#) stepper_z section should be present.
    assert values["stepper_z.position_endstop"] == 0.015


def test_bare_include_sections_do_not_crash():
    values = parse_config_file(gfile("config_a.cfg"))
    assert not any(key.startswith("include gcode_macro.cfg.") for key in values)


def test_garbled_file_raises_config_parse_error():
    with pytest.raises(ConfigParseError):
        parse_config_file(gfile("config_garbled.cfg"))
