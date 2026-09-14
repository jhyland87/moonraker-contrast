from moonraker_contrast.config_diff import diff_text, diff_values


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


def test_diff_text_identical_text():
    text = "[mcu]\nserial: /dev/ttyS0"
    result = diff_text(text, text)
    assert result["identical"] is True
    assert result["hunks"] == []
    assert result["lines_added"] == 0
    assert result["lines_removed"] == 0


def test_diff_text_reports_added_and_removed_lines():
    left = "[mcu]\nserial: /dev/ttyS0\nbaud: 250000"
    right = "[mcu]\nserial: /dev/ttyS1\nbaud: 250000"
    result = diff_text(left, right)
    assert result["identical"] is False
    assert result["lines_added"] == 1
    assert result["lines_removed"] == 1
    assert len(result["hunks"]) == 1

    hunk = result["hunks"][0]
    types = [line["type"] for line in hunk["lines"]]
    assert types == ["context", "remove", "add", "context"]

    removed = next(line for line in hunk["lines"] if line["type"] == "remove")
    assert removed["text"] == "serial: /dev/ttyS0"
    assert removed["left_line"] == 2
    assert removed["right_line"] is None

    added = next(line for line in hunk["lines"] if line["type"] == "add")
    assert added["text"] == "serial: /dev/ttyS1"
    assert added["right_line"] == 2
    assert added["left_line"] is None


def test_diff_text_groups_distant_changes_into_separate_hunks():
    left_lines = [f"line{i}" for i in range(1, 21)]
    right_lines = left_lines.copy()
    right_lines[0] = "changed_line1"
    right_lines[19] = "changed_line20"
    result = diff_text("\n".join(left_lines), "\n".join(right_lines))
    assert result["lines_added"] == 2
    assert result["lines_removed"] == 2
    assert len(result["hunks"]) == 2
