"""Legacy mapping of MythTV action names to UC command names.

Using names matching previous "remote" based integration (8c708a03d5b2 and earlier).
"""

import logging

_LOG = logging.getLogger(__name__)


# Map from MythTV Action to valid UC Remote simple command name.
_COMMAND_MAP = {
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
"""Known mappings per documented recommendations.
As used by previous "remote" based integration (bd0f51e80975 and earlier)."""


def legacy_remote_map_action_name_to_uc_simple_command(action: str) -> str:
    """
    Map from MythTV Action to valid UC Remote simple command name.

    https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_remote.md#simple-commands
    """
    command = action.upper().replace(" ", "_").replace("/", "_")

    if command in _COMMAND_MAP:
        assert len(_COMMAND_MAP[command]) <= 20, f"mapped {command} too long"
        return _COMMAND_MAP[command]

    if len(command) > 20:
        _LOG.warning("Command %s truncated", command)
        command = command[:20]

    return command
