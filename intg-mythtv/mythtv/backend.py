"""
MythTV communication for Remote Two integration.

Using Backend APIs

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import ItemsView

from MythTV.services_api.send import Send

from .frontend import MythTVFrontend


class MythTVBackend(Send):
    """API calls to MythTV backend."""

    _frontends: dict[str, MythTVFrontend]

    def __init__(self, host: str, port: int = 6544, frontend_restart_commands: dict[str, str] | None = None):
        """Initialize the object."""
        super().__init__(host=host, port=port)
        self._log = logging.getLogger(f"{__name__}.{host}")

        if frontend_restart_commands is None:
            frontend_restart_commands = {}

        frontends = self.send("Status/GetBackendStatus")["BackendStatus"]["Frontends"]
        self._log.info("Discovered %d frontends", len(frontends))

        self._frontends = {}
        for f in frontends:
            name = f["Name"].lower()
            self._log.info("Found Frontend: %s", name)
            if name in self._frontends:
                self._log.error("Duplicated frontend!")
                continue
            restart_cmd = frontend_restart_commands.get(name, None)
            frontend = MythTVFrontend(
                name=name,
                host=f["IP"],
                port=f["Port"],
                frontend_restart_command=restart_cmd,
            )
            self._frontends[name] = frontend

    def frontends(self) -> ItemsView[str, MythTVFrontend]:
        """Get all frontends. Name mappping to MythTVFrontend object."""
        return self._frontends.items()
