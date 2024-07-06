from __future__ import annotations

import logging
import os
import io
import re
from io import BufferedReader
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Dict,
    List,
    Union
)

class BambuStudio(object):
    _file: str
    _matched_data = {}
    _parse_reversed: bool = True
    _opt_start_str: str = r"^;.*_config = begin$"
    _opt_end_str: str = r"^;.*_config = end$"

    _opt_aliases = {
        # These associations were taken from the legacy handler, mostly:
        # https://github.com/bambulab/BambuStudio/blob/60a792b76cd39a69970608d6346dd134d20ee663/src/libslic3r/PrintConfig.cpp#L4614-L4739
        "enable_wipe_tower": "enable_prime_tower",
        "wipe_tower_width": "prime_tower_width",
        "bottom_solid_infill_flow_ratio": "initial_layer_flow_ratio",
        "wiping_volume": "prime_volume",
        "wipe_tower_brim_width": "prime_tower_brim_width",
        "tool_change_gcode": "change_filament_gcode",
        "bridge_fan_speed": "overhang_fan_speed",
        "infill_extruder": "sparse_infill_filament",
        "solid_infill_extruder": "solid_infill_filament",
        "perimeter_extruder": "wall_filament",
        "support_material_extruder": "support_filament",
        "support_material_interface_extruder": "support_interface_filament"
        # Todo...
    }
    
    def __init__(self, filename: str, regex_groups: Dict[str, Any]) -> None:
        self._filename = filename
        #self._matched_data = regex_groups
        pass

    @property
    def version(self) -> str|float|None:
        return self._matched_data.get("version", None)

    @property
    def sliced_date(self) -> str|None:
        return None

    @property
    def slicer(self) -> str:
        return self._matched_data.get("slicer", None)

    def parse(self) -> Any:
        print(f"Parsing gcode made by {self._matched_data.get("slicer", None)}")
        print(f"\tReverse parse: {self._parse_reversed}")
        print(f"\tConfig start line: {self._opt_start_str}")
        print(f"\tConfig end line: {self._opt_end_str}")