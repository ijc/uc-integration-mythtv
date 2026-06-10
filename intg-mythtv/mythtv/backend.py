"""
MythTV communication for Remote Two integration.

Using Backend APIs

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from MythTV.services_api.send import Send

from .frontend import MythTVFrontend


class MythTVBackend(Send):
    """API calls to MythTV backend."""

    def __init__(
        self,
        host: str,
        port: int = 6544,
    ):
        """Initialize the object."""
        super().__init__(host=host, port=port)

    def frontend(self, frontend_restart_command: str | None = None) -> MythTVFrontend:
        """Temp."""
        return MythTVFrontend(self.host, 6547, frontend_restart_command)
