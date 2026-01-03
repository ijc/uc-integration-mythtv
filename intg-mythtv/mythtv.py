"""
MythTV communication for Remote Two integration.

Using Frontend Services API: https://www.mythtv.org/wiki/Frontend_Service

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from MythTV.services_api.send import Send
import logging
from dataclasses import dataclass
import json

import requests
from retry import retry

_LOG = logging.getLogger(__name__)


@dataclass
class Command:
    """Represents a MythTV Command/Action."""

    action: str
    """The MythTV Action name"""

    key: str | None
    """The MythTV Key name"""

    desc: str
    """Description"""


# Map from MythTV Action to valid UC Remote simple command name.
COMMAND_MAP = {
    "0": "DIGIT_0",
    "1": "DIGIT_1",
    "2": "DIGIT_2",
    "3": "DIGIT_3",
    "4": "DIGIT_4",
    "5": "DIGIT_5",
    "6": "DIGIT_6",
    "7": "DIGIT_7",
    "8": "DIGIT_8",
    "9": "DIGIT_9",
    "UP": "CURSOR_UP",
    "DOWN": "CURSOR_DOWN",
    "LEFT": "CURSOR_LEFT",
    "RIGHT": "CURSOR_RIGHT",
    "SELECT": "CURSOR_ENTER",
    "BACK": "BACK",
    "VOLUMEDOWN": "VOLUME_DOWN",
    "VOLUMEUP": "VOLUME_UP",
    "MUTE": "MUTE_TOGGLE",
    "STOP": "STOP",
    "SEEKFFWD": "FAST_FORWARD",
    "SEEKRWND": "REWIND",
    # Too long
    "3DTOPANDBOTTOMDISCARD": "3DTOPANDBOTTOMDISCAR",
    "CHANNEL_RECORDING_PRIORITIES": "RECORDING_PRIOS",
    "MANAGE_RECORDING_RULES": "MANAGE_REC_RULES",
    "MANAGE_RECORDINGS___FIX_CONFLICTS": "MANAGE_RECSCONFLICTS",
    "PROGRAM_RECORDING_PRIORITIES": "MANAGE_REC_PRIOS",
    "SWITCHTOPLAYLISTEDITORGALLERY": "PLIST_ED_GALLERY",
    "SWITCHTOPLAYLISTEDITORTREE": "PLIST_ED_TREE",
    "SELECT_MUSIC_PLAYLISTS": "SELECT_MUSIC_PLIST",
    "SHOW_MUSIC_MINIPLAYER": "SHOW_MUSIC_MINI",
    "TV_RECORDING_DELETION": "RECORDING_DELETE",
    "TV_RECORDING_PLAYBACK": "RECORDING_PLAYBACK",
    "TOGGLE_SHOW_WIDGET_BORDERS": "SHOW_WIDGET_BORDERS",
    "TOGGLE_SHOW_WIDGET_NAMES": "SHOW_WIDGET_NAMES",
}
"""Known mappings per documented recommendations"""


ACTION_TO_SEND_KEY_MAP = {
    "UP": "Up",
    "DOWN": "Down",
    "LEFT": "Left",
    "RIGHT": "Right",
    "SELECT": "Enter",
    "ESCAPE": "Escape",
}
"""Maps SendAction commands to SendKey keys"""


def map_action_name_to_uc_simple_command(action: str) -> str:
    """
    Map from MythTV Action to valid UC Remote simple command name.

    https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_remote.md#simple-commands
    """
    command = action.upper().replace(" ", "_").replace("/", "_")

    if command in COMMAND_MAP:
        assert len(COMMAND_MAP[command]) <= 20, f"mapped {command} too long"
        return COMMAND_MAP[command]

    if len(command) > 20:
        _LOG.warning("Command %s truncated", command)
        command = command[:20]

    return command


class MythTV(Send):
    """Control a MythTV frontend."""

    def __init__(
        self,
        host: str,
        port: int = 6547,
    ):
        """Initialize the object."""

        super().__init__(host=host, port=port)

        actions = self._get_action_list()

        self._commands = {
            map_action_name_to_uc_simple_command(action): Command(
                action,
                ACTION_TO_SEND_KEY_MAP.get(action),
                description
            )
            for (action, description) in actions["FrontendActionList"]["ActionList"].items()
        }

    @retry(RuntimeError, tries=30, delay=2)
    def _get_action_list(self):
        """Fetch the actions supported by this host."""
        return self.send("Frontend/GetActionList")

    def commands(self) -> dict[str, Command]:
        """
        Return a mapping of the available actions.

        Keys are action names, values are descriptions.
        """
        return self._commands

    def run_command(self, command):
        """
        Run the named action.

        Returns true if the action succeeded.
        """
        if command not in self._commands:
            _LOG.error("command: %s not found", command)
            return False

        command = self._commands[command]

        if command.key is not None:
            _LOG.debug(
                "command %s mapped to key %s (action:%s)",
                command,
                command.key,
                command.action
            )

            jsondata = {"key": command.key}
            try:
                resp = self.send("Frontend/SendKey", jsondata=jsondata)
            except (RuntimeError, RuntimeWarning) as e:
                _LOG.error("SendKey failed: %s", e)
                return False
        else:
            _LOG.debug("command %s mapped to action %s", command, command.action)

            jsondata = {"action": command.action}
            try:
                resp = self.send("Frontend/SendAction", jsondata=jsondata)
            except (RuntimeError, RuntimeWarning) as e:
                _LOG.error("SendAction failed: %s", e)
                return False

        _LOG.debug(f"response: {json.dumps(resp)}")
        return resp["bool"]
