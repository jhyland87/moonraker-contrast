import sys
from pathlib import Path

import pytest

# Make the src/ layout importable without an editable install.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DATA = Path(__file__).resolve().parent / "data"
DEFAULT_MAPPING = ROOT / "mappings" / "slicer_mappings.cfg"


@pytest.fixture
def data_dir():
    return DATA


@pytest.fixture
def mappings():
    from moonraker_contrast.mapping import load_mappings
    return load_mappings(str(DEFAULT_MAPPING))


def gfile(name):
    return DATA / name
