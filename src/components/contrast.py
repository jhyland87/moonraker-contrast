from __future__ import annotations

import pathlib
import re
import logging
import os.path
import sys
import urllib.parse
import tornado
import tornado.iostream
import tornado.httputil
import tornado.web
from enum import Enum

from io import BufferedReader
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Dict,
    #List,
    #Tuple,
    #TypedDict,
    #Type
)

if TYPE_CHECKING:
    from ..server import Server
    from ..confighelper import ConfigHelper
    from .file_manager.file_manager import FileManager, MetadataStorage

from .slicers.generic_slicer import GenericSlicer 
from .slicers.prusa_slicer import PrusaSlicer 
from .slicers.cura_slicer import CuraSlicer 
from .slicers.orca_slicer import OrcaSlicer 

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

class Contrast:

    """A class for handling all the /server/files/slicer resource endpoints

    This class serves as a function to setup the API endpoint routes; a simple 
    factory for the slicer objects; metadata updater; and the comparison logic
    for gcode slicer options

    Attributes
    ----------
    _server : Server
        instance of Moonrakers Server class, used to interface with other components

    _file_manager : FileManager
        instance of Moonrakers FileManager class

    _gcode_metadata : MetadataStorage
        used to store the MetadataStorage from Moonraker

    _config : ConfigHelper
        instance of Moonrakers ConfigHelper

    Methods
    -------
    _get_metadata(filename)
        Retrieve metadata for a specific gcode file
    """

    # Aliases used in Moonraker metadata that are aliased to the
    # slier class.
    SLICER_ALIASES = {
        "Cura":"CuraSlier",
        "BambuStudio":"BambuSlicer"
   }

    METADATA_OPTS = "slicer_options"
    OPT_COMPARE_L = "left"
    OPT_COMPARE_R = "right"

    _server: Server
    """instance of Moonrakers Server class, used to interface with other components"""

    _file_manager: FileManager
    """instance of Moonrakers FileManager class"""

    _gcode_metadata: MetadataStorage
    """used to store the MetadataStorage from Moonraker"""

    _moonraker_config: ConfigHelper
    """instance of Moonrakers ConfigHelper"""

    def __init__(self, config):
        self._logger = logging.getLogger("slicer")

        self._moonraker_config = config

        self._server = self._moonraker_config.get_server()

        self.name = self._moonraker_config.get_name()

        self._file_manager = self._server.lookup_component("file_manager")
        self._gcodes_root = self._file_manager.get_directory("gcodes")

        self._gcode_metadata = self._file_manager.get_metadata_storage()

        self._server.register_endpoint(
            "/server/files/slicer/configscan", ["POST"], self._handle_slicer_configscan_request)

        self._server.register_endpoint(
            "/server/files/slicer/configdata", ["GET"], self._handle_slicer_configdata_request)

        self._server.register_endpoint(
            "/server/files/slicer/compare", ["GET"], self._handle_slicer_compare_request)

        self._server.register_endpoint(
            "/server/files/slicer/compare/summarize", ["GET"], self._handle_slicer_summarize_request)
    
    async def _handle_slicer_summarize_request(self, web_request: WebRequest) -> Dict:
        """Summarize gcode slicer option comparison web request handler

        Does a simple comparison between the gcodes slicer opts

        Parameter
        ---------
        web_request: WebRequest
            The WebRequest object (from Moonraker)

        Returns
        -------
        result: Any
            The data (ideally object) to be returned
        """

        file_left = web_request.get_str("left")
        file_right = web_request.get_str("right")
        force_scan = web_request.get_boolean("scan", True)

        meta_left = self._get_metadata(file_left)

        if "slicer_options" not in meta_left:
            if not force_scan:
                return {"error": f"No slicer_options found for left file {file_left}"}
            self._retrieve_options(file_left)

            meta_left = self._get_metadata(file_left)
            if "slicer_options" not in meta_left:
                return {"error": f"No slicer_options found for left file {file_left}, and scan did not save slicer_options"}


        options_left = meta_left.get("slicer_options")

        meta_right = self._get_metadata(file_right)

        if "slicer_options" not in meta_right:
            return {"error": f"No slicer_options found in metadata for right file {file_right}"}

        options_right = meta_right.get("slicer_options")

        return self.summarize(options_left, options_right)

    async def _handle_slicer_compare_request(self, web_request: WebRequest) -> Dict:
        """Gcode slicer option comparison web request handler

        Processes any requests to diff two gcode file slicer options.

        Parameter
        ---------
        web_request: WebRequest
            The WebRequest object (from Moonraker)

        Returns
        -------
        result: Any
            The data (ideally object) to be returned
        """

        file_left = web_request.get_str("left")
        file_right = web_request.get_str("right")
        output_format = web_request.get_str("format", None)
        compat_mode = web_request.get_boolean("compatibility", True)
        include_all_options = web_request.get_boolean("all", True)


        meta_left = self._get_metadata(file_left)

        if not meta_left or "slicer_options" not in meta_left:
            return {"error": f"No metadata found for left file {file_left}"}

        options_left = meta_left.get("slicer_options")

        meta_right = self._get_metadata(file_right)

        if not meta_right or "slicer_options" not in meta_right:

            return {"error": f"No slicer_options found in metadata for right file {file_right}"}

        options_right = meta_right.get("slicer_options")

        if output_format == "itemized":
            # Itemized mode will split up the diff in a format that each value is stored under a
            # key that matches the option value
            slicer_right = self._get_slicer_obj(file_right)

            results = {}

            for name_left, value_left in options_left.items():
                option_right = slicer_right.get_option(name_left, True)

                if not option_right or type(option_right) is not dict:
                    
                    if include_all_options is True:
                        # If the opt doesn't exist, but were including everything, then add a new
                        # results entry that has no `right` key, and a null `option_right` (to
                        # indicate that it doesn't exist)
                        results[name_left] = {"left": value_left, "right_opt": None}

                    continue

                value_right =  option_right.get("value", None)

                if value_left == value_right:
                    continue

                result = {"left": value_left, "right": value_right}

                if name_left != option_right.get("name"):
                    name_right = option_right.get("name")

                    result.update(right_opt=name_right)

                    del options_right[name_right]

                results[name_left] =  result

            if include_all_options is True:
                # If there are any keys left in the right config, then those are values that didn't exist on the
                # left (even with aliases). Add those options with no left value.
                for name_right, value_right in options_right.items():
                    results[name_right] = {"left": None, "right": value_right}

            return results
        
        metadata = {"left": meta_left, "right": meta_right}

        results = {"metadata": metadata, "diff": self.diff(options_left, options_right)}
        return results
        
    async def _handle_slicer_configdata_request(self, web_request: WebRequest) -> Dict:
        """Gcode config data retriever web request handler

        Processes any requests to retrieve the processed config data for a file

        Parameter
        ---------
        web_request: WebRequest
            The WebRequest object (from Moonraker)

        Returns
        -------
        result: Dict
            The metadata for the file, along with the "config" item.
        """

        filename = web_request.get_str("filename")
        metadata = self._gcode_metadata.get(filename, None)

        if not metadata:
            return {"error": f"No metadata found for gcode file {filename}"}

        return {"slicer": metadata.get("slicer", None), 
                "slicer_version": metadata.get("slicer_version"), 
                "slicer_options": metadata.get("slicer_options", None)}

    async def _handle_slicer_configscan_request(self, web_request: WebRequest) -> Dict:
        """Gcode config data scanner web request handler

        Processes any requests to process the config data for a file

        Parameter
        ---------
        web_request: WebRequest
            The WebRequest object (from Moonraker)

        Returns
        -------
        result: Dict
            The metadata for the file, along with the "config" item.
        """
        
        args = web_request.get_args()
        filename = web_request.get_str("filename")
        save = web_request.get_boolean("save", True)
        slicer_module = self._get_slicer_obj(filename)

        slicer_module.parse()

        metadata = self._gcode_metadata.get(filename, None)
     
        slicer_name = metadata.get("slicer")

        self._logger.info(f"Done parsing {filename} with {slicer_name} gcode options processor")

        if save:
            self._update_metadata(filename, {"slicer_options":slicer_module.get_options()})

        return {"filename":filename,
                "slicer":slicer_name, 
                "slicer_version":metadata.get("slicer_version", None),
                "slicer_options":slicer_module.get_options()}


    def _retrieve_options(self, filename: str, save: bool = True):
        slicer_module = self._get_slicer_obj(filename)

        slicer_module.parse()

        metadata = self._gcode_metadata.get(filename, None)
     
        slicer_name = metadata.get("slicer")

        self._logger.info(f"Done parsing {filename} with {slicer_name} gcode options processor")

        if save:
            self._update_metadata(filename, {"slicer_options":slicer_module.get_options()})

        return {"filename":filename,
                "slicer":slicer_name, 
                "slicer_version":metadata.get("slicer_version", None),
                "slicer_options":slicer_module.get_options()}

    def _get_metadata(self, filename: str) -> Optional[Dict]:
        """Retrieve metadata for a specific gcode file

        Using Moonrakers file_manager.get_metadata_storage() method, retrieve the metadata
        for the specified file.

        Parameter
        ---------
        filename: str
            Gcode filename to get metadata for

        Returns
        -------
        result: Dict[str, Any]
            The metadata dictionary
        """

        filename = filename.split("/")[-1]
        metadata = self._gcode_metadata.get(filename, None)

        if not metadata: 
            return {"error": f"No metadata found for gcode file {filename}"}

        return metadata

    def _update_metadata(self, filename: str, data: Dict) -> Optional[Dict]:
        """Update metadata with object via filename

        Update the metadata for a file using Moonrakers file_manager.get_metadata_storage() 
        method.

        Parameter
        ---------
        filename: str
            Gcode filename to apply the updated metadata to

        data: Optional[Dict]
           The new data to apply to this files metadata.

        Returns
        -------
        result: Dict[str, Any]
            The updated metadata dictionary for this file
        """
        
        metadata = self._get_metadata(filename);

        if not metadata: 
            return None;

        metadata.update(data)

        self._gcode_metadata.insert(filename, metadata.copy())

        return metadata;

    def _get_slicer_obj(self, filename: str):
        """Gcode config data scanner web request handler

        This is basically a simple factory method used to check for what slicer was used
        on the specified gcode file, and returns an instance of the corresponding Slicer
        class  (PrusaSlicer, CuraSlicer, etc).

        Parameter
        ---------
        filename: str
            Gcode filename to analyze and create slicer instance for

        Returns
        -------
        result
            The PrusaSlicer/CuraSlicer/etc class used to process this specific gcode
        """
        
        metadata = self._get_metadata(filename)

        if not metadata:
            return {"error":f"No metadata found for {filename}"}

        slicer_name = metadata.get("slicer")

        if slicer_name not in globals():
            return {"error":f"No config parser class found for slicer {slicer_name}"}

        self._logger.info(f"Gcode file {filename} was sliced with {slicer_name}")


        file_path = f"{self._gcodes_root}/{filename}"

        return globals()[slicer_name]( 
                filename=file_path, 
                server=self._server, 
                logging=logging 
            )
    
    def summarize(self, left: Dict, right: Dict) -> Dict:
        left_options = set(left.keys())
        right_options = set(right.keys())

        shared_keys = left_options.intersection(right_options)
        added = left_options-right_options
        removed = right_options-left_options

        modified = {option: (left[option], right[option]) for option in shared_keys if left[option] != right[option]}
        same = set(option for option in shared_keys if left[option] == right[option])

        return {
            "added":list(added), 
            "removed":list(removed),
            "modified":dict(modified),
            "same":list(same)
        }

    def diff(self, left: Dict, right: Dict) -> Dict:
        """
        Diff two dictionary data objects

        Parameter
        ---------
        left: Dict[str, str]
            Dictionary with the key/values for the slicer options in the gcode data

        right: Dict[str, str]
            Same thing as left, but for a different file

        Returns: Dict
            left: Dict[str, str]: Values in the left dict that differ from the right

        Returns
        -------
        left: Dict[str, str]
            Slicer options that are different than the value on the right side

        right: Dict[str, str]
            Slicer options that are different than the value on the left side

        opt_names: list[str]
            Unique list of slier option names that were found in the diff results

        Dict[left|right, Dict[option: str, value: str]]
        """

        result = {}

        left_set = set(left.items())
        right_set = set(right.items())

        result["left"] = left_set - right_set
        result["right"] = right_set - left_set

        updated_keys = list(result["left"])
        updated_keys.extend(list(result["right"]))

        result["left"] = self._sort_dict(dict(result["left"]))
        result["right"] = self._sort_dict(dict(result["right"]))
        result["opt_names"] = sorted(list(dict(updated_keys)))

        return result

    def _sort_dict(self, data: Dict) -> Dict:
        return dict(sorted(data.items()))

def load_component(config: ConfigHelper) -> Contrast:
    return Contrast(config)