"""Moonraker component shim for moonraker-contrast.

This is the ONLY file symlinked into ``moonraker/components/``. It imports the
pip-installed ``moonraker_contrast`` library and exposes two endpoints over both
the HTTP REST API and the JSON-RPC websocket.

Install (handled by install.sh)::

    pip install -e ~/moonraker-contrast        # into Moonraker's venv
    ln -sf ~/moonraker-contrast/component/slicer_compare.py \\
           <moonraker pkg>/components/slicer_compare.py

moonraker.conf::

    [slicer_compare]
    mapping_path: ~/printer_data/config/slicer_mappings.cfg
    float_tolerance: 1e-6

Note: the ``from ..common import ...`` imports only resolve when this file is
loaded as ``moonraker.components.slicer_compare`` inside a running Moonraker, so
``relative-beyond-top-level`` is disabled for standalone linting.
"""
# pylint: disable=relative-beyond-top-level

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

from moonraker_contrast import api
from moonraker_contrast.errors import ContrastError

from ..common import RequestType, TransportType

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper
    from ..common import WebRequest
    from .file_manager.file_manager import FileManager


class SlicerCompare:
    """Moonraker component exposing the slicer-settings compare/scan endpoints."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.file_manager: FileManager = self.server.lookup_component(
            "file_manager"
        )

        mapping_path = config.get(
            "mapping_path", "~/printer_data/config/slicer_mappings.cfg"
        )
        self.float_tolerance = config.getfloat("float_tolerance", 1e-6)
        # MappingStore hot-reloads when the .cfg mtime changes, so users can
        # edit mappings without restarting Moonraker.
        self.mapping_store = api.MappingStore(mapping_path)

        self.server.register_endpoint(
            "/server/slicer/compare",
            RequestType.POST,
            self._handle_compare,
            transports=TransportType.all(),
        )
        self.server.register_endpoint(
            "/server/slicer/settings",
            RequestType.GET,
            self._handle_settings,
            transports=TransportType.all(),
        )
        logging.info("[slicer_compare] component loaded (mapping=%s)", mapping_path)

    def _resolve(self, relative_path: str):
        """Resolve a gcode-root-relative path to an existing absolute Path."""
        if not relative_path:
            raise self.server.error("missing required gcode filename", 400)
        path = self.file_manager.get_full_path("gcodes", relative_path)
        if not path.is_file():
            raise self.server.error(f"gcode file not found: {relative_path}", 404)
        return path

    def _get_mappings(self):
        try:
            return self.mapping_store.get()
        except ContrastError as exc:
            raise self.server.error(str(exc), getattr(exc, "http_status", 500))

    async def _handle_compare(self, web_request: WebRequest) -> Dict[str, Any]:
        left_file = web_request.get_str("file1")
        right_file = web_request.get_str("file2")
        include_same = web_request.get_boolean("include_same", False)
        left_path = self._resolve(left_file)
        right_path = self._resolve(right_file)
        try:
            return api.compare_files(
                left_path, right_path, self._get_mappings(),
                float_tolerance=self.float_tolerance,
                include_same=include_same,
                left_name=left_file, right_name=right_file,
            )
        except ContrastError as exc:
            raise self.server.error(str(exc), getattr(exc, "http_status", 400))

    async def _handle_settings(self, web_request: WebRequest) -> Dict[str, Any]:
        relative_path = web_request.get_str("file")
        path = self._resolve(relative_path)
        try:
            return api.scan_file(
                path, self._get_mappings(), display_name=relative_path
            )
        except ContrastError as exc:
            raise self.server.error(str(exc), getattr(exc, "http_status", 400))


def load_component(config: ConfigHelper) -> SlicerCompare:
    """Moonraker entry point: instantiate and return the component."""
    return SlicerCompare(config)
