from __future__ import annotations

import logging
import os
import json
import re
import sys
from io import BufferedReader
from .generic_slicer import GenericSlicer


"""
Cura string replacements:
    Printer definitions: https://github.com/Ultimaker/Cura/blob/master/resources/definitions/fdmprinter.def.json
    Extruder definitions: https://github.com/Ultimaker/Cura/blob/master/resources/definitions/fdmextruder.def.json
"""

class CuraSlicer(GenericSlicer):
    _parse_reversed = True
    _options_end_pattern = None
    _options_start_pattern = ";End of Gcode"

    _option_aliases = {
        "retraction_length":"retract_length",
        "retract_length":"retraction_amount",
        "retract_speed":"retraction_speed",
        "infill_speed":"speed_print",
        "travel_speed":"speed_travel",
        #"max_volumetric_speed":"",
        #filament_max_volumetric_speed ="",
        "line_width":"extrusion_width",
        "material_print_speed":"max_print_speed",
        "speed_print_layer_0":"speed_layer_0",
        "initial_layer_speed":"speed_layer_0",
        "first_layer_speed":"speed_layer_0",
        #?? = "speed_support_infill",
        # the elephants foot comp is inverse (- value for cura,
        # positive for most other slicers)
        "elefant_foot_compensation":"xy_offset_layer_0",
        "first_layer_size_compensation":"xy_offset_layer_0",
        "first_layer_temperature":"material_print_temperature_layer_0",
        "overhang_fan_speed":"bridge_fan_speed",
        "sparse_infill_density":"infill_sparse_density",
        "brim_separation":"brim_gap"
    }

    _alias_modifiers = {
        ("elefant_foot_compensation", "xy_offset_layer_0"): lambda option_value: self._invert_number(option_value),
        ("brim_separation", "brim_gap"): lambda option_value: self._invert_number(option_value)
    }
    
    # Gcode parser for config
    def parse(self):
        # Since Cura stores them in INI format, which is in JSON format, which is all smushed together on
        # a few lines (why?!), we need to grab that crap data and turn it into something useful. 
        #     1) Grab each option line and return the `;SETTING_n` prefix
        #     2) Concatenate all the lines
        #     3) Use a JSON parser for the new string value
        #     4) Grab the values from each object in the JSON object (which may be an array of objects, or
        #         an array with an array of objects).
        #     5) Split the results by \n, and use regex to match for `key = value` format
        #     6) Add each key/value to the self._options dictionary
        raw_options = list()
        with open(self._filename, "rb") as file_handle:
            segment = None
            offset = 0
            end_of_options = False
            file_handle.seek(0, os.SEEK_END)
            file_size = remaining_size = file_handle.tell()

            while remaining_size > 0 and end_of_options is False:
                offset = min(file_size, offset + self._buffer_size)
                file_handle.seek(file_size - offset)
                buffer = file_handle.read(min(remaining_size, self._buffer_size))

                # remove file's last "\n" if it exists, only for the first buffer
                if remaining_size == file_size and buffer[-1] == ord("\n"):
                    buffer = buffer[:-1]

                remaining_size -= self._buffer_size
                lines = buffer.split("\n".encode())

                
                # yield lines in this chunk except the segment
                for line in reversed(lines):
                    decoded_line = line.decode()

                    if ( decoded_line == self._options_end_pattern):
                        end_of_options = True
                        break

                    parsed_line = re.match(r"^;SETTING_(?P<gcode_version>[0-9]) (?P<line>.+)$", decoded_line)
                    if not parsed_line: 
                        break

                    detected_gcode_version = parsed_line.group("gcode_version")

                    new_line = parsed_line.group("line")
                    raw_options.insert(0, new_line)

        raw_options = "".join(raw_options)
        gcode_json = json.loads(raw_options)
        gcode_sections = []

        for a in gcode_json.values():
            if isinstance(a, str):
                gcode_sections.append(a)
            elif isinstance(a, list):
                for b in a:
                    gcode_sections.append(b)

        data = "".join(gcode_sections)

        for line in data.split("\\n"):
            line_data = re.match(r"^(?P<key>.*) = (?P<val>.*)$", line.strip())
            if line_data:
                # Add this to the gcode config, finally..
                self._options[line_data.group("key")] =  self._cast(line_data.group("val"))


if __name__ == "__main__" and __package__ is None:
    __package__ = "cura_slicer"