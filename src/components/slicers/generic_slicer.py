from __future__ import annotations

#import logging
import os
import re
import sys
from io import BufferedReader
from enum import Enum
from collections.abc import Sequence, Callable
#from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Callable,
    Coroutine,
    Type,
    TypeVar,
    Union,
    Dict,
    List,
    Awaitable
)

if TYPE_CHECKING:
    from logging import Logger
    from ...server import Server
    from ...confighelper import ConfigHelper
    from ..file_manager.file_manager import FileManager, MetadataStorage

class GenericSlicer(object):
    IterStatus = Enum('IterStatus', ['NONE', 'BEGIN', 'END', 'ERROR'])
    _filename: str
    _cast_values: bool = True
    _parse_reversed: bool = True
    _buffer_size: int = 8192

    # These begin/end lines match PrusaSlicer and most of their legacy versions.
    _options_start_pattern: Optional[str] = r"^;.*_config = begin$"
    _options_end_pattern: Optional[str] = r"^;.*_config = end$"

    # Used to determine the status of the parser (has it started? ended? found anything? etc). This is
    # useful since we go over the options line by line, and not always in the same direction.
    _parse_status: Dict 

    # Used to ignore any slicer opts that aren't really that important (eg: thumbnails)
    _ignore_options: List = []

    # Store the aliased option names to make comparison with different versions possible (hopefully)
    #     KEY: The alias option name
    #     VALUE: The primary option name
    #         TODO: Try to find a way to map all the different slicer option names and map them to
    #               a common set of names that can be used to compare values across different slicers.
    _option_aliases: Dict = {}

    # if a comparison is done with compatibility enabled, any slicer option configs that are compared to
    # aliased values, they can also be modified by creating a lambda function here with the local option
    # name as the root key, then the aliased key in the nested dictionary
    _alias_modifiers: Dict = {}

    _logger: Logger
    _file_manager: FileManager
    _metadata: MetadataStorage
    _file_metadata: Dict = {} 

    # The gcode slicer options will get stored here.
    _options: Dict = {}
    
    def __init__(self, filename: str, server: Server, logging: Logger) -> None:
        self._logger = logging.getLogger(self.__class__.__name__);

        if not server:
            self._logger.error("No moonraker server object provided")
            return;

        if not os.path.isfile(filename):
            self._logger.error("No moonraker server object provided")
            return;

        self._server = server
        self._file_manager = self._server.lookup_component("file_manager")
        self._gcode_root = self._file_manager.get_directory("gcodes")
        self._filename = filename.split("/")[-1]
        self._logger.info(f"Loading gcode file {self._filename}")
        self._metadata = self._file_manager.get_metadata_storage()
        self._file_metadata = self._metadata.get(self._filename, None)
        self._options = self._file_metadata.get("slicer_options", None)

    @property 
    def file(self):
    	return self._filename

    # This is used to iterate over the file from the top down
    def _gcode_reader(self):
        pass

    # This is used to iterate over the file from the bottom up
    def _reverse_gcode_reader(self):
        in_options = False
        is_completed = False
        options_count = 0
        #gcode_settings = {}

        try:
            """A generator that returns the lines of a file in reverse order"""
            with open(self._filename, "rb") as file_handle:
                segment = None
                offset = 0
                file_handle.seek(0, os.SEEK_END)
                file_size = remaining_size = file_handle.tell()

                while remaining_size > 0:
                    offset = min(file_size, offset + buf_size)
                    file_handle.seek(file_size - offset)
                    buffer = file_handle.read(min(remaining_size, buf_size))

                    # remove file's last "\n" if it exists, only for the first buffer
                    if remaining_size == file_size and buffer[-1] == ord("\n"):
                        buffer = buffer[:-1]

                    remaining_size -= buf_size
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

                        # If we've come across the beginning line (or prusaslicer_config = 'end'), 
                        # then verify this was the first time.
                        if this_line is self.IterStatus.BEGIN:
                            if in_options is True:
                                raise ValueError("Encountered the beginning line while already in slicer options")

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
                raise EOFError("No slicer options found")

    def set_option(self, name: str, value: Optional[str|float|int] = None) -> None:
        self._options.update({name: value})

    # Get value by name. This will also use any aliased names if the name isn't found in the gcode opts
    # dictionary.
    def get_option(self, name: str, aliases: bool = False) -> Any:
        # If there's no options with this name in the _options, then check if there's an
        # alias for it, and use that if so.

        # If the name key DOES exist in the local slicer opts data, return it
        if name in self._options:
            return {
                "name":name, 
                "value":self._options.get(name, None)
            }

        # If it doesn't, then check to see if it has an alias, if not then return None
        if name not in self._option_aliases:
            return None

        # An alias is found, then do the same _options check for that opt
        alias_name = self._option_aliases.get(name, None)

        # If the alias isn't in the local gcode slicer opts, then just return None
        if alias_name not in self._options:
            return None

        # Then see if that alias exists in the gcode slicer opts data
        alias_value = self._options.get(alias_name, None)

        # See if the alias has a modifier
        modifier_index = (alias_name, name)
        if modifier_index not in self._alias_modifiers:
            # If not, then just return the aliased name and opt value
            return {
                "name":alias_name, 
                "value":alias_value
            }

        # If a modifier lambda function is found, then use it to modify the opt value
        alias_modifier = self._alias_modifiers.get(modifier_index, None)

        # And that its callable
        if callable(alias_modifier):
            return {
                "name":alias_name, 
                "value":alias_modifier(alias_value)
            }

        return {
            "name":alias_name, 
            "value":alias_value
        }

    def _aliased_value(self, foreign_option: str, local_option: str, value: str|int|float|bool) -> Optional[str|int|float|bool]:
        #_value = value
        _value = self.get_option(local_option)
        modifier = self._alias_modifiers.get((foreign_option, local_option), None)

        if not modifier: 
            return value

        if callable(modifier):
            return modifier(value)

        # If the modifier object is a dictionary, then return that value if its present
        if type(modifier) is dict:
            return modifier.get(value, value) 

        return value

    def is_options_line(self, line: str) -> bool|None:
        pass

    # This is given a line to determine if it matches the end of the settings block or not.
    def is_options_end(self, line: str):
        # If the slicer stores the settings at the bottom of the file (ie: were parsing in reverse), and
        # for some reason, they don't include a "config_end" phrase, then were best off just returning
        # None, or returning True if we can tell the fd pointer is at the end of the file.
        if not self._options_end_pattern:
            # Todo: Return TRUE if were at the end of the file and the config_end_str is empty
            return None

        if re.match(self._options_end_pattern, line.strip()):
            return True

        return False

    # This is given a line to determine if it matches the beginning of the settings block or not.
    def is_options_start(self, line: str):
    
        if not self._options_start_pattern:
            # Todo: Return TRUE if were at the end of the file and the config_end_str is empty
            return None

        if re.match(self._options_start_pattern, line.strip()):
            return True

        return False

    def parse(self) -> Any:
        pass

    def get_options(self):
        return self._options

    def _parse_line(self, line: str) -> List:
        if not line:
            return

        parsed_line = re.match(r"^[\s;]*([a-zA-Z0-9_\s-]+) = (.+)$", line)

        # If no matches are found, then  abort
        if not parsed_line: return None

        # If there was a key and value found, return them
        if parsed_line[1] and parsed_line[2]: 
            return {parsed_line[1]: self._cast(parsed_line[2])}

    # Check if a string value is a decimal/float value
    def _is_dec(self, value: str) -> bool:
        """ Check if a string value is a decimal/float value """

        float_match = re.match(r"^\-?([0-9]+)\.([0-9]+)$", value)

        return float_match is not None

    # Cast a string value to its appropriate data type.
    def _cast(self, value: str) -> Any:
        """ Cast a string value to its appropriate data type. """

        result = None
        data_type = None

        if type(value) is not str:
            return value

        value = value.strip()

        if value.lower() == "true": return True
        if value.lower() == "false": return False
        if value in ("none",""): return None

        try:
            if self._is_dec(value) is True:
                result = float(value)
                data_type = type(result)
                return result
        except:
            pass

        try:
            result = int(value)
            data_type = type(result)
            return result
        except:
            pass

        return value
        

    def _percent_to_float(self, value: Optional[str]) -> float:
        """Convert a percentage value to a float (ratio) (75% -> 0.75)"""

        if not value or type(value) is not str:
            return

        if not value.endswith("%"):
            return

        return float(value.strip("%"))/100


    def _float_to_percent(self, value: Optional[str|int|float]) -> str:
        """Convert a float value (ratio) to a percentage (0.75 -> 75%)"""

        if not value:
            return

       	return str(int(value * 100))+"%"

    def _float_percent_match(self, 
                             percent_value: [str|int|float], 
                             float_value: [str|int|float]
                             ) -> bool:
        """Compare a percent value with a ratio value.

        Examples:
            self._float_percent_match('75%', 0.65) == False

            self._float_percent_match('75%', 0.75) == True
        """

        # _float_percent_match('75%', 0.65)
        if type(percent_value) is type(float_value): 
            return bool(percent_value == float_value)

        percent_value = str(percent_value)
        float_value = str(float_value)
        if percent_value.endswith("%"): 
            percent_value = self._percent_to_float(percent_value)

        if float_value.endswith("%"): 
            float_value = self._percent_to_float()

        return bool(float(percent_value) == float(float_value))

    # Convert a numerical value to an int if it won't change the value, otherwise return an int
    def _to_float_or_int(self, value: int|float|str) -> float|int:
        try:
            if (float_value := float(value)) == (int_value := int(float_value)):
                return int_value

            return float_value
        except:
            return value

    # Method to invert a numerical value (eg: one slicer takes a positive compensation value, the other
    # takes an "expansion" value that would require a negative value). 
    # This method also handles the casting
    def _invert_number(self, value: int|float|str):
        number = self._to_float_or_int(value)

        return -number

#if __name__ == "__main__" and __package__ is None:
__package__ = "generic_slicer"
__spec__ = 'GenericSlicer'
__name__ = 'GenericSlicer'
__path__ = 'slicers.generic_slicer'