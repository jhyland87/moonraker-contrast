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

from .slicers.base_slicer  import BaseSlicer 
from .slicers.prusa_slicer import PrusaSlicer 
from .slicers.cura_slicer  import CuraSlicer 
from .slicers.orca_slicer  import OrcaSlicer 

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

class Slicer:

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

    _config: ConfigHelper
    """instance of Moonrakers ConfigHelper"""

    def __init__(self, config):
        self._logger = logging.getLogger("slicer")

        self._config = config

        self._server = self._config.get_server()

        self.name = self._config.get_name()

        self._file_manager = self._server.lookup_component("file_manager")

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

        file_l = web_request.get_str("left")
        file_r = web_request.get_str("right")
        scan = web_request.get_boolean("scan", True)
        gcodes_dir = self._file_manager.get_directory("gcodes")

        meta_l = self._get_metadata(file_l)

        if "slicer_options" not in meta_l:
            if not scan:
                return {"error": f"No slicer_options found for left file {file_l}"}
            self._retrieve_opts(file_l)

            meta_l = self._get_metadata(file_l)
            if "slicer_options" not in meta_l:
                return {"error": f"No slicer_options found for left file {file_l}, and scan did not save slicer_options"}


        opts_l = meta_l.get("slicer_options")

        meta_r = self._get_metadata(file_r)

        if "slicer_options" not in meta_r:
            return {"error": f"No slicer_options found in metadata for right file {file_r}"}

        opts_r = meta_r.get("slicer_options")

        return self.summarize(opts_l, opts_r)

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

        file_l = web_request.get_str("left")
        file_r = web_request.get_str("right")
        out_fmt = web_request.get_str("format", None)
        compat_mode = web_request.get_boolean("compatibility", True)
        inc_all = web_request.get_boolean("all", True)

        gcodes_dir = self._file_manager.get_directory("gcodes")

        meta_l = self._get_metadata(file_l)

        if not meta_l or "slicer_options" not in meta_l:
            return {"error": f"No metadata found for left file {file_l}"}

        opts_l = meta_l.get("slicer_options")

        meta_r = self._get_metadata(file_r)

        if not meta_r or "slicer_options" not in meta_r:

            return {"error": f"No slicer_options found in metadata for right file {file_r}"}

        opts_r = meta_r.get("slicer_options")

        if out_fmt == "itemized":
            # Itemized mode will split up the diff in a format that each value is stored under a
            # key that matches the option value
            slicer_r = self._get_slicer_obj(file_r)

            results = {}

            for name_l, value_l in opts_l.items():
                opt_r = slicer_r.get_opt(name_l, True)

                if not opt_r or type(opt_r) is not dict:
                    
                    if inc_all is True:
                        # If the opt doesn't exist, but were including everything, then add a new
                        # results entry that has no `right` key, and a null `opt_r` (to
                        # indicate that it doesn't exist)
                        results[name_l] = {"left": value_l, "right_opt": None}

                    continue

                value_r =  opt_r.get("value", None)

                if value_l == value_r:
                    continue

                result = {"left": value_l, "right": value_r}

                if name_l != opt_r.get("name"):
                    name_r = opt_r.get("name")

                    result.update(right_opt=name_r)

                    del opts_r[name_r]

                results[name_l] =  result

            if inc_all is True:
                # If there are any keys left in the right config, then those are values that didn't exist on the
                # left (even with aliases). Add those options with no left value.
                for name_r, value_r in opts_r.items():
                    results[name_r] = {"left": None, "right": value_r}

            return results
        
        metadata = {"left": meta_l, "right": meta_r}

        results = {"metadata": metadata, "diff": self.diff(opts_l, opts_r)}
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


    def _retrieve_opts(self, filename: str, save: bool = True):
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

        gcodes_dir = self._file_manager.get_directory("gcodes")

        file_path = f"{gcodes_dir}/{filename}"

        return globals()[slicer_name]( 
                filename=file_path, 
                server=self._server, 
                logging=logging 
            )
    
    def summarize(self, left: Dict, right: Dict) -> Dict:
        opts_l = set(left.keys())
        opts_r = set(right.keys())

        shared_keys = opts_l.intersection(opts_r)
        added = opts_l-opts_r
        removed = opts_r-opts_l

        modified = {o: (left[o], right[o]) for o in shared_keys if left[o] != right[o]}
        same = set(o for o in shared_keys if left[o] == right[o])

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

def load_component(config: ConfigHelper) -> Slicer:
    return Slicer(config)