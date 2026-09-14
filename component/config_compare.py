"""Moonraker component shim for the config-file compare resource.

This is the ONLY file symlinked into ``moonraker/components/`` for this resource.
It imports the pip-installed ``moonraker_contrast`` library and exposes two
endpoints over both the HTTP REST API and the JSON-RPC websocket, mirroring
``slicer_compare.py`` but for whole Klipper/Moonraker config files (``printer.cfg``,
``moonraker.conf``, etc.) instead of slicer settings embedded in gcode.

Install (handled by install.sh)::

    pip install -e ~/moonraker-contrast        # into Moonraker's venv
    ln -sf ~/moonraker-contrast/component/config_compare.py \\
           <moonraker pkg>/components/config_compare.py

moonraker.conf::

    [config_compare]
    float_tolerance: 1e-6

Note: the ``from ..common import ...`` imports only resolve when this file is
loaded as ``moonraker.components.config_compare`` inside a running Moonraker, so
``relative-beyond-top-level`` is disabled for standalone linting.
"""
# pylint: disable=relative-beyond-top-level

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

from moonraker_contrast import config_api
from moonraker_contrast.errors import ContrastError

from ..common import RequestType, TransportType

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper
    from ..common import WebRequest
    from .file_manager.file_manager import FileManager

_VALID_MODES = {"text", "values"}


class ConfigCompare:
    """Moonraker component exposing the config-file compare/scan endpoints."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.file_manager: FileManager = self.server.lookup_component(
            "file_manager"
        )
        self.float_tolerance = config.getfloat("float_tolerance", 1e-6)

        self.server.register_endpoint(
            "/server/config/compare",
            RequestType.POST,
            self._handle_compare,
            transports=TransportType.all(),
        )
        self.server.register_endpoint(
            "/server/config/settings",
            RequestType.GET,
            self._handle_settings,
            transports=TransportType.all(),
        )
        logging.info("[config_compare] component loaded")

    def _resolve(self, relative_path: str):
        """Resolve a config-root-relative path to an existing absolute Path."""
        if not relative_path:
            raise self.server.error("missing required config filename", 400)
        path = self.file_manager.get_full_path("config", relative_path)
        if not path.is_file():
            raise self.server.error(f"config file not found: {relative_path}", 404)
        return path

    async def _handle_compare(self, web_request: WebRequest) -> Dict[str, Any]:
        left_file = web_request.get_str("file1")
        right_file = web_request.get_str("file2")
        mode = web_request.get_str("mode", "values")
        if mode not in _VALID_MODES:
            raise self.server.error(
                f"invalid mode {mode!r}, expected one of {sorted(_VALID_MODES)}", 400
            )
        left_path = self._resolve(left_file)
        right_path = self._resolve(right_file)
        try:
            return config_api.compare_config_files(
                left_path, right_path,
                mode=mode,
                float_tolerance=self.float_tolerance,
                left_name=left_file, right_name=right_file,
            )
        except ContrastError as exc:
            raise self.server.error(str(exc), getattr(exc, "http_status", 400))

    async def _handle_settings(self, web_request: WebRequest) -> Dict[str, Any]:
        relative_path = web_request.get_str("file")
        path = self._resolve(relative_path)
        try:
            return config_api.scan_config_file(path, display_name=relative_path)
        except ContrastError as exc:
            raise self.server.error(str(exc), getattr(exc, "http_status", 400))


def load_component(config: ConfigHelper) -> ConfigCompare:
    """Moonraker entry point: instantiate and return the component."""
    return ConfigCompare(config)
