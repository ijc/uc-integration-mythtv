"""
MythTV communication for Remote Two integration.

Using Backend APIs

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging

from MythTV.services_api.send import Send

from .frontend import MythTVFrontend

_LOG = logging.getLogger(__name__)


class MythTVBackend(Send):
    """API calls to MythTV backend."""

    def __init__(
        self,
        host: str,
        port: int = 6544,
    ):
        """Initialize the object."""
        super().__init__(host=host, port=port)

        frontends = self.send("Status/GetBackendStatus")["BackendStatus"]["Frontends"]

        self._frontends = {}
        for f in frontends:
            _LOG.debug("Frontend: %s", f)
            name = f["Name"]
            frontend = MythTVFrontend(host=f["IP"], port=f["Port"])
            self._frontends[name] = frontend

    def frontend(self, frontend_restart_command: str | None = None) -> MythTVFrontend:
        """Temp."""
        return MythTVFrontend(self.host, 6547, frontend_restart_command)
