"""
MythTV communication for Remote Two integration.

Using Frontend Services API: https://www.mythtv.org/wiki/Frontend_Service

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import json
import logging
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from subprocess import DEVNULL
from typing import Tuple

import ucapi
from MythTV.services_api.send import Send
from mythtv_legacy_remote import legacy_remote_map_action_name_to_uc_simple_command
from retry import retry
from ucapi import media_player


class MythTVCommandKind(Enum):
    """The kind of a command."""

    MEDIA_PLAYER = "media_player"
    """Command is a UC media player command"""

    SIMPLE = "simple"
    """Command is a UC simple command"""

    SYSTEM_COMMAND = "system_command"
    """Command is a system command"""


@dataclass
class MythTVCommand:
    """Represents a MythTV Command/Action."""

    action: str
    """The MythTV Action name"""

    key: str | None
    """The MythTV Key name"""

    desc: str
    """Description"""

    kind: MythTVCommandKind
    """The Kind of Command this is"""


FRONTEND_RESTART_SYSTEM_COMMAND = "RESTART_FRONTEND"

# curl -H 'Accept: application/json'  http://mythtv:6547/Frontend/GetActionList  | jq .FrontendActionList.ActionList
# https://github.com/unfoldedcircle/integration-python-library/blob/main/ucapi/media_player.py
MYTHTV_ACTION_TO_UC_MEDIA_PLAYER_COMMAND_MAP: dict[str, media_player.Commands] = {
    #: media_player.Commands.ON,
    #: media_player.Commands.OFF,
    #: media_player.Commands.TOGGLE,
    #: media_player.Commands.PLAY_PAUSE,
    "STOP": media_player.Commands.STOP,
    "SEEKRWND": media_player.Commands.PREVIOUS,
    "SEEKFFWD": media_player.Commands.NEXT,
    "FFWD": media_player.Commands.FAST_FORWARD,
    "RWND": media_player.Commands.REWIND,
    #: media_player.Commands.SEEK, -- takes a param
    #: media_player.Commands.VOLUME, -- takes a param
    "VOLUMEDOWN": media_player.Commands.VOLUME_DOWN,
    "VOLUMEUP": media_player.Commands.VOLUME_UP,
    "MUTE": media_player.Commands.MUTE_TOGGLE,
    #: media_player.Commands.MUTE,
    #: media_player.Commands.UNMUTE,
    # "": media_player.Commands.REPEAT, -- takes a param
    # "": media_player.Commands.SHUFFLE, -- takes a param
    "CHANNELDOWN": media_player.Commands.CHANNEL_UP,
    "CHANNELUP": media_player.Commands.CHANNEL_DOWN,
    "UP": media_player.Commands.CURSOR_UP,
    "DOWN": media_player.Commands.CURSOR_DOWN,
    "LEFT": media_player.Commands.CURSOR_LEFT,
    "RIGHT": media_player.Commands.CURSOR_RIGHT,
    "SELECT": media_player.Commands.CURSOR_ENTER,
    "0": media_player.Commands.DIGIT_0,
    "1": media_player.Commands.DIGIT_1,
    "2": media_player.Commands.DIGIT_2,
    "3": media_player.Commands.DIGIT_3,
    "4": media_player.Commands.DIGIT_4,
    "5": media_player.Commands.DIGIT_5,
    "6": media_player.Commands.DIGIT_6,
    "7": media_player.Commands.DIGIT_7,
    "8": media_player.Commands.DIGIT_8,
    "9": media_player.Commands.DIGIT_9,
    "MENURED": media_player.Commands.FUNCTION_RED,
    "MENUGREEN": media_player.Commands.FUNCTION_GREEN,
    "MENUYELLOW": media_player.Commands.FUNCTION_YELLOW,
    "MENUBLUE": media_player.Commands.FUNCTION_BLUE,
    "Main Menu": media_player.Commands.HOME,
    "MENU": media_player.Commands.MENU,
    #: media_player.Commands.CONTEXT_MENU,
    "GUIDE": media_player.Commands.GUIDE,
    "INFO": media_player.Commands.INFO,
    # "BACK": media_player.Commands.BACK,
    "ESCAPE": media_player.Commands.BACK,
    #: media_player.Commands.SELECT_SOURCE, -- takes a param
    #: media_player.Commands.SELECT_SOUND_MODE, -- takes a param
    #: media_player.Commands.RECORD,
    "TV Recording Playback": media_player.Commands.MY_RECORDINGS,
    "Live TV": media_player.Commands.LIVE,
    "EJECT": media_player.Commands.EJECT,
    #: media_player.Commands.OPEN_CLOSE,
    #: media_player.Commands.AUDIO_TRACK,
    "TOGGLESUBTITLE": media_player.Commands.SUBTITLE,
    #: media_player.Commands.SETTINGS,
    #: media_player.Commands.SEARCH,
}
"""Map from MythTV Action to valid UC MediaPlayer command name."""

MYTHTV_ACTION_TO_MEDIA_PLAYER_SIMPLE_COMMAND_MAP: dict[str, str] = {
    # Too long
    "3DTOPANDBOTTOMDISCARD": "3DTOPANDBOTTOMDISCAR",
    "Channel Recording Priorities": "RECORDING_PRIOS",
    "Manage Recording Rules": "MANAGE_REC_RULES",
    "Manage Recordings / Fix Conflicts": "MANAGE_RECSCONFLICTS",
    "Program Recording Priorities": "MANAGE_REC_PRIOS",
    "SWITCHTOPLAYLISTEDITORGALLERY": "PLIST_ED_GALLERY",
    "SWITCHTOPLAYLISTEDITORTREE": "PLIST_ED_TREE",
    "Select music playlists": "SELECT_MUSIC_PLIST",
    "Show Music Miniplayer": "SHOW_MUSIC_MINI",
    "TV Recording Deletion": "RECORDING_DELETE",
    # "TV Recording Playback": "RECORDING_PLAYBACK",
    "Toggle Show Widget Borders": "SHOW_WIDGET_BORDERS",
    "Toggle Show Widget Names": "SHOW_WIDGET_NAMES",
}
"""Map from MythTV Action to valid UC MediaPlayer simple command name."""


MYTHTV_SEND_ACTION_TO_SEND_KEY_MAP = {
    "UP": "Up",
    "DOWN": "Down",
    "LEFT": "Left",
    "RIGHT": "Right",
    "SELECT": "Enter",
    "ESCAPE": "Escape",
}
"""Maps SendAction commands to SendKey keys"""


def map_mythtv_action_name_to_uc_command(
    log: logging.Logger, action: str
) -> Tuple[media_player.Commands | str, MythTVCommandKind]:
    """
    Map from MythTV Action to valid UC Media Player command name.

    https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_media_player.md#commands
    """
    if action in MYTHTV_ACTION_TO_UC_MEDIA_PLAYER_COMMAND_MAP:
        media_player_command = MYTHTV_ACTION_TO_UC_MEDIA_PLAYER_COMMAND_MAP[action]
        assert len(media_player_command) <= 20, f"mapped media player command {media_player_command} too long"
        return media_player_command, MythTVCommandKind.MEDIA_PLAYER

    if action in MYTHTV_ACTION_TO_MEDIA_PLAYER_SIMPLE_COMMAND_MAP:
        command = MYTHTV_ACTION_TO_MEDIA_PLAYER_SIMPLE_COMMAND_MAP[action]
        assert len(command) <= 20, f"mapped simple {command} too long"
    else:
        command = action.upper().replace(" ", "_").replace("/", "_")
        if len(command) > 20:
            log.warning("Action %s truncated", action)
            command = command[:20]

    return command, MythTVCommandKind.SIMPLE


class MythTVFrontend(Send):
    """Control a MythTV frontend."""

    def __init__(
        self,
        name: str,
        host: str,
        port: int = 6547,
        frontend_restart_command: str | None = None,
    ):
        """Initialize the object."""
        super().__init__(host=host, port=port)
        self._log = logging.getLogger(f"{__name__}.{name}")

        actions = self._get_action_list()

        def make_mythtv_command(action: str, description: str) -> Tuple[media_player.Commands | str, MythTVCommand]:
            uc_command, kind = map_mythtv_action_name_to_uc_command(self._log, action)
            return (
                uc_command,
                MythTVCommand(action, MYTHTV_SEND_ACTION_TO_SEND_KEY_MAP.get(action), description, kind),
            )

        self._commands: dict[media_player.Commands | str, MythTVCommand] = dict(
            [
                make_mythtv_command(action, description)
                for (action, description) in actions["FrontendActionList"]["ActionList"].items()
            ]
        )

        self._legacy_remote_command_map: dict[str, str] = dict(
            filter(
                lambda kv: kv[0] != kv[1],
                [
                    (legacy_remote_map_action_name_to_uc_simple_command(mythtv_command.action), cmd_id)
                    for cmd_id, mythtv_command in self._commands.items()
                ],
            )
        )
        # for k, v in self._legacy_remote_command_map.items():
        #     print(f"Legacy: {k:20} -> {v}")

        if frontend_restart_command is not None:
            self._log.info("Restart Command: %s", frontend_restart_command)
            self._commands[FRONTEND_RESTART_SYSTEM_COMMAND] = MythTVCommand(
                frontend_restart_command, None, "Restart mythfrontend", MythTVCommandKind.SYSTEM_COMMAND
            )

    @retry(RuntimeError, tries=30, delay=2)
    def _get_action_list(self):
        """Fetch the actions supported by this host."""
        return self.send("Frontend/GetActionList")

    def commands(self) -> dict[str, MythTVCommand]:
        """
        Return a mapping of the available actions.

        Keys are Unfolded circle command names, values are MythTVCommands.
        """
        return self._commands

    def run_command(self, cmd_id: str):
        """
        Run the named action.

        Returns true if the action succeeded.
        """
        command = self._commands.get(cmd_id)
        if not command:
            if (mapped_legacy_remote_command := self._legacy_remote_command_map.get(cmd_id)) is not None:
                self._log.warning(
                    "Mapped legacy remote command %s to UC command %s", cmd_id, mapped_legacy_remote_command
                )
                cmd_id = mapped_legacy_remote_command
                command = self._commands.get(cmd_id)

        if not command:
            self._log.error("command: %s not found", cmd_id)
            return ucapi.StatusCodes.NOT_FOUND

        self._log.info("UC commmand %s mapped to %s", cmd_id, command)

        if command.kind == MythTVCommandKind.SYSTEM_COMMAND:
            self._log.debug("system command: %s", command.action)
            resp = run_system_command(command.action)
        elif command.key is not None:
            self._log.debug("SendKey %s (action:%s)", command.key, command.action)

            jsondata = {"key": command.key}
            try:
                resp = self.send("Frontend/SendKey", jsondata=jsondata)
            except (RuntimeError, RuntimeWarning) as e:
                self._log.error("SendKey failed: %s", e)
                return ucapi.StatusCodes.SERVER_ERROR
        else:
            self._log.debug("SendAction %s", command.action)

            jsondata = {"action": command.action}
            try:
                resp = self.send("Frontend/SendAction", jsondata=jsondata)
            except (RuntimeError, RuntimeWarning) as e:
                self._log.error("SendAction failed: %s", e)
                return ucapi.StatusCodes.SERVER_ERROR

        self._log.debug("response: %s", json.dumps(resp))
        if not resp["bool"]:
            return ucapi.StatusCodes.SERVER_ERROR

        return ucapi.StatusCodes.OK


def run_system_command(command: str):
    """Run the given command."""
    args = shlex.split(command)
    r = subprocess.run(
        args,
        stdin=DEVNULL,
        shell=False,
        check=False,
    )

    return {"bool": r.returncode == 0}
