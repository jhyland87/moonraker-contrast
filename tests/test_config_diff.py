from moonraker_contrast.config_diff import diff_raw, diff_values


def test_diff_values_changed_only_left_only_right_same():
    left = {"a": 1, "b": 2, "only_left_key": 3}
    right = {"a": 1, "b": 5, "only_right_key": 4}
    result = diff_values(left, right, 1e-6)
    assert result["same_keys"] == ["a"]
    assert result["changed"]["b"] == {"left": 2, "right": 5}
    assert result["only_left"] == {"only_left_key": 3}
    assert result["only_right"] == {"only_right_key": 4}


def test_diff_values_float_tolerance():
    result = diff_values({"x": 0.2}, {"x": 0.20000001}, 1e-6)
    assert result["same_keys"] == ["x"]
    assert result["changed"] == {}


def test_diff_raw_identical_text():
    text = "[mcu]\nserial: /dev/ttyS0\n"
    result = diff_raw(text, text, "a.cfg", "b.cfg")
    assert result["identical"] is True
    assert result["diff"] == ""
    assert result["lines_added"] == 0
    assert result["lines_removed"] == 0


def test_diff_raw_reports_added_and_removed_lines():
    left = "[mcu]\nserial: /dev/ttyS0\nbaud: 250000\n"
    right = "[mcu]\nserial: /dev/ttyS1\nbaud: 250000\n"
    result = diff_raw(left, right, "a.cfg", "b.cfg")
    assert result["identical"] is False
    assert result["lines_added"] == 1
    assert result["lines_removed"] == 1
    assert "a.cfg" in result["diff"]
    assert "b.cfg" in result["diff"]
