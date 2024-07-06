from __future__ import annotations

import os
import json
import re
import sys
from enum import Enum
from io import BufferedReader
from .generic_slicer import GenericSlicer

class PrusaSlicer(GenericSlicer):
    # These begin/end lines match PrusaSlicer and most of their legacy versions.
    _options_start_pattern = r"^;.*_config = begin$"
    _options_end_pattern = r"^;.*_config = end$"

    """Slicer configuration key aliases (for legacy or possible slicer cross compatibility)"""
    _option_aliases = {
        # ALIAS_NAME: NAME_USED_IN_THIS_SLICER
        # https://github.com/supermerill/SuperSlicer/blob/9f87f80cae9b613d91a3cc581661e98d5b597605/src/libslic3r/PrintConfig.cpp#L8000-L8012
        # 
        # Sources for below values:
        #	- https://github.com/Ultimaker/Cura/blob/abf9fef334387b01c7d054bff5ea3f2247ff6926/plugins/VersionUpgrade/VersionUpgrade21to22/VersionUpgrade21to22.py#L129
        #   - https://github.com/prusa3d/PrusaSlicer/blob/fd02400245df25f1286059aa642739660df76663/src/libslic3r/PrintConfig.cpp#L4738-L4831
        #   - https://github.com/theophile/SuperSlicer_to_Orca_scripts/blob/main/superslicer_to_orca.pl#L337-L632
        "enable_arc_fitting":"arc_fitting",
        "bottom_layer_speed_ratio":"bottom_layer_speed",
        "first_layer_height_ratio":"first_layer_height",
        "initial_layer_print_height":"first_layer_height",
        "bottom_layer_speed":"first_layer_speed",
        "skirt_height":"draft_shieldprint_host",
        "octoprint_host":"print_host",
        "octoprint_cafile":"printhost_cafile",
        "octoprint_apikey":"printhost_apikey",
        "preset_name":"preset_names",
        "extrusion_spacing":"extrusion_width",
        "perimeter_extrusion_spacing":"perimeter_extrusion_width",
        "inner_wall_line_width":"perimeter_extrusion_width",
        "external_perimeter_extrusion_spacing":"external_perimeter_extrusion_width",
        "infill_extrusion_spacing":"infill_extrusion_width",
        "solid_infill_extrusion_spacing":"solid_infill_extrusion_width",
        "internal_solid_infill_line_width":"solid_infill_extrusion_width",
        "top_infill_extrusion_spacing":"top_infill_extrusion_width",
        "fill_top_flow_ratio":"top_infill_extrusion_width",
        "top_solid_infill_flow_ratio":"top_infill_extrusion_width",
        "bed_size":"bed_shape",
        "first_layer_size_compensation":"elefant_foot_compensation",
        "xy_offset_layer_0":"elefant_foot_compensation",
        #"z_steps_per_mm":"z_step",
        #"infill_not_connected":"infill_connection",
        #"seam_travel":"seam_travel_cost",
        "print_machine_envelope":"machine_limits_usage",
        #"retract_lift_not_last_layer":"retract_lift_top", # retract_lift_above retract_lift_below?
        "sla_archive_format":"output_format",
        "support_material_solid_first_layer":"raft_first_layer_density",
        "bottom_shell_layers":"bottom_solid_layers",
        "bottom_shell_thickness":"bottom_solid_min_thickness",
        "bridge_no_support":"dont_support_bridges",
        "brim_object_gap":"brim_separation",
        "brim_gap":"brim_separation",
        "detect_overhang_wall":"overhangs",
        "detect_thin_wall":"thin_walls",
        "enable_overhang_speed":"enable_dynamic_overhang_speeds",
        "enable_prime_tower":"wipe_tower",
        "filter_out_gap_fill":"gap_fill_enabled",
        "gap_fill_min_length":"gap_fill_enabled",
        "emit_machine_limits_to_gcode":"machine_limits_usage",
        "infill_direction":"fill_angle",
        "infill_wall_overlap":"infill_overlap",
        "is_infill_first":"infill_first",
        "line_width":"extrusion_width",
        "print_flow_ratio":"extrusion_multiplier",
        "initial_layer_acceleration":"first_layer_acceleration",
        "first_layer_extrusion_spacing":"first_layer_extrusion_width",
        "interface_shells":"interface_shells",
        "internal_solid_infill_acceleration":"solid_infill_acceleration",
        "ironing_flow":"ironing_flowrate",
        "ironing_spacing":"ironing_spacing",
        "spiral_mode":"spiral_vase",
        "solid_infill_filament":"solid_infill_extruder",
        "support_filament":"support_material_extruder",
        "sparse_infill_filament":"infill_extruder",
        "wall_filament":"perimeter_extruder",
        "support_interface_filament":"support_material_interface_extruder",
        "max_travel_detour_distance":"avoid_crossing_perimeters_max_detour",
        "minimum_sparse_infill_area":"solid_infill_below_area",
        "extra_perimeters_overhangs":"extra_perimeters_on_overhangs",
        "inner_wall_acceleration":"perimeter_acceleration",
        "outer_wall_acceleration":"external_perimeter_acceleration",
        "outer_wall_line_width":"external_perimeter_extrusion_width",
        "prime_tower_brim_width":"wipe_tower_brim_width",
        "prime_tower_width":"wipe_tower_width",
        "reduce_crossing_wall":"avoid_crossing_perimeters",
        "reduce_infill_retraction":"only_retract_when_crossing_perimeters",
        "skirt_loops":"skirts",
        "sparse_infill_acceleration":"infill_acceleration",
        "sparse_infill_density":"fill_density",
        "sparse_infill_line_width":"infill_extrusion_width",
        "enable_support":"support_material",
        "support_angle":"support_material_angle",
        "enforce_support_layers":"support_material_enforce_layers",
        "support_base_pattern_spacing":"support_material_spacing",
        "support_top_z_distance":"support_material_contact_distance",
        "support_bottom_z_distance":"support_material_bottom_contact_distance",
        "support_interface_bottom_layers":"support_material_bottom_interface_layers",
        "support_interface_loop_pattern":"support_material_interface_contact_loops",
        "support_interface_spacing":"support_material_interface_spacing",
        "support_interface_top_layers":"support_material_interface_layers",
        "support_line_width":"support_material_extrusion_width",
        "support_on_build_plate_only":"support_material_buildplate_only",
        "support_threshold_angle":"support_material_threshold",
        "top_shell_thickness":"top_solid_min_thickness",
        "top_surface_acceleration":"top_solid_infill_acceleration",
        "top_surface_line_width":"top_infill_extrusion_width",
        "min_width_top_surface":"top_infill_extrusion_width",
        "tree_support_branch_angle":"support_tree_angle",
        "tree_support_angle_slow":"support_tree_angle_slow",
        "tree_support_branch_diameter":"support_tree_branch_diameter",
        "tree_support_branch_diameter_double_wall":"support_tree_branch_diameter_angle",
        "tree_support_tip_diameter":"support_tree_tip_diameter",
        "tree_support_top_rate":"support_tree_top_rate",
        "wall_generator":"perimeter_generator",
        "wall_loops":"perimeters",
        "xy_inner_size_compensation":"xy_size_compensation",
        "sparse_infill_pattern":"fill_pattern",
        "solid_fill_pattern":"fill_pattern",
        "internal_solid_infill_pattern":"fill_pattern",
        "filename_format":"output_filename_format",
        "support_base_pattern":"support_material_pattern",
        "top_surface_pattern":"top_fill_pattern",
        "support_object_xy_distance":"support_material_xy_spacing",
        "fuzzy_skin_point_distance":"fuzzy_skin_point_dist",
        "fuzzy_skin_thickness":"fuzzy_skin_thickness",
        "bottom_surface_pattern":"bottom_fill_pattern",
        "bridge_flow":"bridge_flow_ratio",
        "first_layer_flow_ratio":"first_layer_extrusion_width",
        "bottom_solid_infill_flow_ratio":"first_layer_extrusion_width",
        "infill_combination":"infill_every_layers",
        "print_sequence":"complete_objects",
        "support_style":"support_material_style",
        "disable_m73":"remaining_times",
        # Filament
        "cool_plate_temp":"bed_temperature",
        "hot_plate_temp":"bed_temperature",
        "textured_plate_temp":"bed_temperature",
        "eng_plate_temp":"bed_temperature",
        "overhang_fan_speed":"bridge_fan_speed",
        "close_fan_the_first_x_layers":"disable_fan_first_layers",
        "filament_end_gcode":"end_filament_gcode",
        #"external_perimeter_fan_speed":"",
        #"overhang_fan_threshold":"",
        "filament_flow_ratio":"extrusion_multiplier",
        "reduce_fan_stop_start_freq":"fan_always_on",
        "fan_cooling_layer_time":"fan_below_layer_time",
        "default_filament_colour":"filament_colour",
        "filament_deretraction_speed":"filament_deretract_speed",
        "filament_retraction_minimum_travel":"filament_retract_before_travel",
        "filament_retract_before_wipe":"filament_retract_before_wipe",
        "filament_retract_when_changing_layer":"filament_retract_layer_change",
        "filament_retraction_length":"filament_retract_length",
        "filament_z_hop":"filament_retract_lift",
        "filament_retraction_speed":"filament_retract_speed",
        "hot_plate_temp_initial_layer":"first_layer_bed_temperature",
        "cool_plate_temp_initial_layer":"first_layer_bed_temperature",
        "eng_plate_temp_initial_layer":"first_layer_bed_temperature",
        "textured_plate_temp_initial_layer":"first_layer_bed_temperature",
        "nozzle_temperature_initial_layer":"first_layer_temperature",
        "fan_max_speed":"max_fan_speed",
        "fan_min_speed":"min_fan_speed",
        "slow_down_min_speed":"min_print_speed",
        "slow_down_layer_time":"slowdown_below_layer_time",
        "filament_start_gcode":"start_filament_gcode",
        "nozzle_temperature":"temperature",
        # Printer
        "before_layer_change_gcode":"before_layer_gcode",
        "change_filament_gcode":"toolchange_gcode",
        "deretraction_speed":"deretract_speed",
        "layer_change_gcode":"layer_gcode",
        "change_extrusion_role_gcode":"toolchange_gcode",
        "feature_gcode":"toolchange_gcode",
        "machine_end_gcode":"end_gcode",
        "machine_pause_gcode":"pause_print_gcode",
        "machine_start_gcode":"start_gcode",
        "printable_area":"bed_shape",
        "printable_height":"max_print_height",
        "retract_when_changing_layer":"retract_layer_change",
        "retraction_length":"retract_length",
        "z_hop":"retract_lift",
        "retraction_hop_enabled":"retract_lift",
        "retraction_hop":"retract_lift",
        #"retract_lift_top":"",
        #"retract_lift_enforce":"",
        "retraction_minimum_travel":"retract_before_travel",
        "retraction_speed":"retract_speed",
        "skin_overlap":"infill_overlap",
        #"skirt_line_width":"",
        #"skirt_brim_line_width":"",
        "skirt_minimal_length":"min_skirt_length",
        "skirt_brim_minimal_length":"min_skirt_length",
        #"skirt_speed":"",
        #"skirt_brim_speed":"",
        "speed_support_infill":"support_material_speed",
        "speed_support_lines":"support_material_speed",
        "speed_support_roof":"support_material_interface_speed",
        # top_solid_infill_speed support_material_speed ??
        "speed_support_interface":"support_material_interface_speed",
        #"support_roof_density":"support_material_spacing",
        #"support_interface_density":"support_material_interface_layers",
        #"support_roof_enable":"interface_shells",
        #"support_interface_enable":"support_material_interface_layers",
        "support_interface_extruder_nr":"support_material_interface_extruder",
        "support_roof_extruder_nr":"support_material_interface_extruder",
        "support_roof_line_distance":"support_material_contact_distance",
        "support_interface_line_distance":"support_material_interface_spacing",
        "support_roof_line_width":"support_material_extrusion_width",
        "support_interface_line_width":"support_material_extrusion_width",
        "support_roof_pattern":"top_fill_pattern",
        "support_interface_pattern":"support_material_interface_pattern"
    }
    
    # if a comparison is done with compatibility enabled, any slicer option configs that are compared to
    # aliased values, they can also be modified by creating a lambda function here with the local option
    # name as the root key, then the aliased key in the nested dictionary
    _alias_modifiers = {
        ("first_layer_size_compensation","elefant_foot_compensation"): lambda option_value: self._invert_number(option_value),
        ("xy_offset_layer_0","elefant_foot_compensation"): lambda option_value: self._invert_number(option_value),
        ("brim_gap", "brim_separation"): lambda option_value: self._invert_number(option_value)
    }
   

    # TODO: Possibly methods to make the values comparable to other similar slicer options in
    #         other slicers that use a different format.
    #         - Cura has "first layer horizontal expansion" (`xy_offset_layer_0`), which
    #           can be used to compensate for elephants foot, but requires a negative value.
    #           But PrusaSlier has `elefant_foot_compensation` which does the same thing, 
    #           but takes a positive value.
    #         - Current versions of PrusaSlicer uses a percentage as the `fill_density` 
    #           value while older versions use a decimal value (this is converted in
    #           the `PrintConfigDef::handle_legacy` method)
    
    def parse(self):
        parsed_options = {}

        # Iterate over each line yielded from the _reverse_gcode_reader generator, adding each
        # to the parsed_options dictionary if needed.
        for line in self._reverse_gcode_reader():
            if type(line) is dict:
                # If the key returned is in the ignore_options, then skip it.
                option_name = list(line).pop(0)
                if self._ignore_options and option_name in self._ignore_options:
                    self._logger.info(f"{option_name} WAS fund in self._ignore_options, skipping")
                    continue

                parsed_options.update(line)

        self._options = parsed_options

    def _reverse_gcode_reader(self):
        in_options = False
        is_completed = False
        options_count = 0
        try:
            """A generator that returns the lines of a file in reverse order"""
            with open(f"{self._gcode_root}/{self._filename}", "rb") as file_handle:
                segment = None
                offset = 0
                file_handle.seek(0, os.SEEK_END)
                file_size = remaining_size = file_handle.tell()

                while remaining_size > 0:
                    offset = min(file_size, offset + self._buffer_size)
                    file_handle.seek(file_size - offset)
                    buffer = file_handle.read(min(remaining_size, self._buffer_size))

                    # remove file's last "\n" if it exists, only for the first buffer
                    if remaining_size == file_size and buffer[-1] == ord("\n"):
                        buffer = buffer[:-1]

                    remaining_size -= self._buffer_size
                    lines = buffer.split("\n".encode())

                    # append last chunk's segment to this chunk's last line
                    if segment is not None:
                        lines[-1] += segment

                    segment = lines[0]
                    lines = lines[1:]

                    # yield lines in this chunk except the segment
                    for line in reversed(lines):
                        # only decode on a parsed line, to avoid utf-8 decode error
                        this_line = self._handle_line(line)

                        # If we've reached the ending line (which is the line that contains 
                        # prusaslicer_config = 'begin' since were reading it in reverse order), 
                        # then determine what exception to raise..
                        if this_line is self.IterStatus.END:
                            # if we've somehow come here without ever having hit the begin
                            # line, then raise an EOF.
                            if in_options is False:
                                raise EOFError("Encountered ending line without ever being in the footer")

                            # Otherwise, end the generator
                            raise GeneratorExit("Encountered ending")

                        # If we've come across the beginning line (or prusaslicer_config = 'end"), 
                        # then verify this was the first time.
                        if this_line is self.IterStatus.BEGIN:
                            if in_options is True:
                                raise ValueError("Encountered the beginning line while already in options")

                            in_options = True
                            continue

                        if type(this_line) is dict:
                            options_count = options_count+1
                            yield this_line

                # Don't yield None if the file was empty
                if segment is not None:
                    this_line = self._handle_line(segment)
                    if this_line is self.IterStatus.END:
                        raise GeneratorExit("Encountered ending")

                    if type(this_line) is dict:
                        options_count = options_count+1
                        yield this_line

        except GeneratorExit as ge:
            pass
        finally:
            if options_count == 0:
                raise EOFError("No options found")

    def _parse_line(self, line:str):
        if not line:
            return

        m = re.match(r"^; (?P<key>[a-zA-Z0-9_-]+) = (?P<val>.+)", str(line))

        if not m: return None

        # If there was a key and value found, return them
        if m.group("key") and m.group("val"): 
            return {m.group("key"): self._cast(m.group("val")) if self._cast_values else m.group("val")}

    def _handle_line(self, line):
        line = line.decode("utf-8")

        if self.is_options_start(line):
            return self.IterStatus.END

        if self.is_options_end(line):
            return self.IterStatus.BEGIN

        parsed_line = self._parse_line(line=line)

        if parsed_line is None:
            return self.IterStatus.NONE

        return parsed_line


if __name__ == "__main__" and __package__ is None:
    __package__ = "slicers.prusa_slicer.PrusaSlicer"