from moonraker_contrast.compare import diff, values_equal
from moonraker_contrast.mapping import NormalizedConfig


def make_config(canonical=None, passthrough=None, provenance=None):
    return NormalizedConfig(
        canonical=canonical or {},
        passthrough=passthrough or {},
        provenance=provenance or {},
    )


def test_values_equal_float_tolerance():
    assert values_equal(0.2, 0.20000001, 1e-6)
    assert not values_equal(0.2, 0.3, 1e-6)
    assert values_equal("0.20", 0.2, 1e-6)


def test_values_equal_boolish():
    assert values_equal(1, "true", 1e-6)
    assert values_equal(0, "false", 1e-6)
    assert not values_equal(1, 0, 1e-6)


def test_changed_bucket():
    provenance = {"layer_height": "layer_height"}
    left = make_config(canonical={"layer_height": 0.2}, provenance=provenance)
    right = make_config(canonical={"layer_height": 0.3}, provenance=provenance)
    result = diff(left, right, 1e-6)
    assert "layer_height" in result["changed"]
    assert result["changed"]["layer_height"]["left"]["value"] == 0.2
    assert result["changed"]["layer_height"]["right"]["value"] == 0.3
    assert result["same_keys"] == []


def test_same_bucket():
    left = make_config(canonical={"x": 0.2}, provenance={"x": "x"})
    right = make_config(canonical={"x": 0.2}, provenance={"x": "x"})
    result = diff(left, right, 1e-6)
    assert result["same_keys"] == ["x"]
    assert result["changed"] == {}


def test_only_left_and_only_right():
    left = make_config(passthrough={"a": 1})
    right = make_config(passthrough={"b": 2})
    result = diff(left, right, 1e-6)
    assert "a" in result["only_left"]
    assert "b" in result["only_right"]


def test_cross_slicer_canonical_match_records_raw_keys():
    # first_layer_height (prusa) vs initial_layer_print_height (orca), same value.
    left = make_config(
        canonical={"first_layer_height": 0.2},
        provenance={"first_layer_height": "first_layer_height"},
    )
    right = make_config(
        canonical={"first_layer_height": 0.2},
        provenance={"first_layer_height": "initial_layer_print_height"},
    )
    result = diff(left, right, 1e-6)
    assert "first_layer_height" in result["same_keys"]


def test_canonical_flag_on_changed():
    left = make_config(
        canonical={"first_layer_height": 0.2},
        provenance={"first_layer_height": "first_layer_height"},
    )
    right = make_config(
        canonical={"first_layer_height": 0.3},
        provenance={"first_layer_height": "initial_layer_print_height"},
    )
    result = diff(left, right, 1e-6)
    entry = result["changed"]["first_layer_height"]
    assert entry["canonical"] is True
    assert entry["left"]["raw_key"] == "first_layer_height"
    assert entry["right"]["raw_key"] == "initial_layer_print_height"
