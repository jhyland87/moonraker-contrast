from conftest import gfile

from moonraker_contrast.detect import detect_slicer, read_regions


def _detect(filename):
    header, footer = read_regions(gfile(filename))
    return detect_slicer(header, footer)


def test_detect_prusaslicer():
    info = _detect("prusa_footer.gcode")
    assert info is not None
    assert info.name == "PrusaSlicer"
    assert info.family == "prusa"
    assert info.config_location == "footer"
    assert info.version.startswith("2.7.1")


def test_detect_superslicer():
    info = _detect("super_footer.gcode")
    assert info.name == "SuperSlicer"
    assert info.family == "prusa"
    assert info.version.startswith("2.5.59")


def test_detect_orcaslicer():
    info = _detect("orca_footer.gcode")
    assert info.name == "OrcaSlicer"
    assert info.family == "prusa"
    assert info.config_location == "footer"


def test_detect_bambustudio():
    info = _detect("bambu_header.gcode")
    assert info.name == "BambuStudio"
    assert info.family == "bambu"
    assert info.config_location == "header"
    assert info.version == "1.9.0"


def test_cura_is_unsupported():
    assert _detect("cura_unsupported.gcode") is None


def test_bambu_not_misclassified_as_prusa():
    # Precedence: a Bambu header must never be read as a prusa-family slicer.
    info = _detect("bambu_header.gcode")
    assert info.family == "bambu"
