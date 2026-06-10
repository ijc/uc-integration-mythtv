##!/usr/bin/env python3
"""
Remote Two integration driver for MythTV.

:copyright: (c) 2023-2024 by Unfolded Circle ApS.
:copyright: (c) Ian Campbell.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os
import signal
from typing import Any, Tuple

import config
import ucapi
from mythtv import MythTVBackend, MythTVCommand, MythTVFrontend
from ucapi import MediaPlayer, media_player, remote

_LOG = logging.getLogger("driver")  # avoid having __main__ in log messages
_LOOP = asyncio.new_event_loop()

# Global variables
api = ucapi.IntegrationAPI(_LOOP)
_MYTHTV: dict[str, MythTVFrontend] = {}


@api.listens_to(ucapi.Events.CONNECT)
async def on_connect():
    """When the UCR2 connects, all configured MythTV frontends are getting connected."""
    await api.set_device_state(ucapi.DeviceStates.CONNECTED)  # just to make sure the device state is set


@api.listens_to(ucapi.Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids) -> None:
    """When the UCR2 subscribes, assume entities are on."""
    for entity_id in entity_ids:
        api.configured_entities.update_attributes(
            entity_id,
            {
                media_player.Attributes.STATE: media_player.States.ON,
                # media_player.Attributes.MEDIA_TITLE: "TESTING 123",
                # media_player.Attributes.MEDIA_TYPE: media_player.MediaType.TVSHOW,
                # media_player.Attributes.MEDIA_IMAGE_URL:
                # 'http://iranon:6544/Content/GetPreviewImage?ChanId=5105&StartTime=2025-12-26T17:59:00Z&Width=360',
            },
        )


async def media_player_cmd_handler(
    entity: ucapi.MediaPlayer, cmd_id: str, params: dict[str, Any] | None
) -> ucapi.StatusCodes:
    """Command handler.

    Called by the integration-API if a command is sent to a configured MediaPlayer-entity.

    :param entity: MediaPlayer entity
    :param cmd_id: command
    :param params: optional command parameters
    :return: status of the command
    """
    _LOG.debug("command: %s %s", cmd_id, params if params else "")

    mtv = _MYTHTV.get(entity.id)

    if mtv is None:
        return ucapi.StatusCodes.BAD_REQUEST

    if cmd_id == remote.Commands.SEND_CMD:
        _LOG.warning("Handling legacy remote SEND_CMD")
        if params is None or "command" not in params:
            _LOG.error("Malformed arguments to SEND_CMD")
            return ucapi.StatusCodes.BAD_REQUEST
        cmd_id = params["command"]

    return mtv.run_command(cmd_id)


# https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_media_player.md#features
# https://github.com/unfoldedcircle/integration-python-library/blob/main/ucapi/media_player.py
FEATURE_REQUIRED_COMMANDS: dict[media_player.Features, set[media_player.Commands]] = {
    media_player.Features.ON_OFF: set(
        [
            media_player.Commands.ON,
            media_player.Commands.OFF,
        ]
    ),
    media_player.Features.TOGGLE: set([media_player.Commands.TOGGLE]),
    media_player.Features.VOLUME: set([media_player.Commands.VOLUME]),
    media_player.Features.VOLUME_UP_DOWN: set(
        [
            media_player.Commands.VOLUME_DOWN,
            media_player.Commands.VOLUME_UP,
        ]
    ),
    media_player.Features.MUTE_TOGGLE: set([media_player.Commands.MUTE_TOGGLE]),
    media_player.Features.MUTE: set([media_player.Commands.MUTE]),
    media_player.Features.UNMUTE: set([media_player.Commands.UNMUTE]),
    media_player.Features.PLAY_PAUSE: set([media_player.Commands.PLAY_PAUSE]),
    media_player.Features.STOP: set([media_player.Commands.STOP]),
    media_player.Features.NEXT: set([media_player.Commands.NEXT]),
    media_player.Features.PREVIOUS: set([media_player.Commands.PREVIOUS]),
    media_player.Features.FAST_FORWARD: set([media_player.Commands.FAST_FORWARD]),
    media_player.Features.REWIND: set([media_player.Commands.REWIND]),
    media_player.Features.REPEAT: set([media_player.Commands.REPEAT]),
    media_player.Features.SHUFFLE: set([media_player.Commands.SHUFFLE]),
    media_player.Features.SEEK: set([media_player.Commands.SEEK]),
    # Announcements:
    # media_player.Features.MEDIA_DURATION: set([]),
    # media_player.Features.MEDIA_POSITION: set([]),
    # media_player.Features.MEDIA_TITLE: set([]),
    # media_player.Features.MEDIA_ARTIST: set([]),
    # media_player.Features.MEDIA_ALBUM: set([]),
    # media_player.Features.MEDIA_IMAGE_URL: set([]),
    # media_player.Features.MEDIA_TYPE: set([]),
    media_player.Features.DPAD: set(
        [
            media_player.Commands.CURSOR_UP,
            media_player.Commands.CURSOR_DOWN,
            media_player.Commands.CURSOR_LEFT,
            media_player.Commands.CURSOR_RIGHT,
            media_player.Commands.CURSOR_ENTER,
        ]
    ),
    media_player.Features.NUMPAD: set(
        [
            media_player.Commands.DIGIT_0,
            media_player.Commands.DIGIT_1,
            media_player.Commands.DIGIT_2,
            media_player.Commands.DIGIT_3,
            media_player.Commands.DIGIT_4,
            media_player.Commands.DIGIT_5,
            media_player.Commands.DIGIT_6,
            media_player.Commands.DIGIT_7,
            media_player.Commands.DIGIT_8,
            media_player.Commands.DIGIT_9,
        ]
    ),
    media_player.Features.HOME: set([media_player.Commands.HOME]),
    media_player.Features.MENU: set([media_player.Commands.MENU, media_player.Commands.BACK]),
    media_player.Features.CONTEXT_MENU: set([media_player.Commands.CONTEXT_MENU]),
    media_player.Features.GUIDE: set([media_player.Commands.GUIDE]),
    media_player.Features.INFO: set([media_player.Commands.INFO]),
    media_player.Features.COLOR_BUTTONS: set(
        [
            media_player.Commands.FUNCTION_RED,
            media_player.Commands.FUNCTION_GREEN,
            media_player.Commands.FUNCTION_YELLOW,
            media_player.Commands.FUNCTION_BLUE,
        ]
    ),
    media_player.Features.CHANNEL_SWITCHER: set(
        [
            media_player.Commands.CHANNEL_UP,
            media_player.Commands.CHANNEL_DOWN,
        ]
    ),
    media_player.Features.SELECT_SOURCE: set([media_player.Commands.SELECT_SOURCE]),
    media_player.Features.SELECT_SOUND_MODE: set([media_player.Commands.SELECT_SOUND_MODE]),
    media_player.Features.EJECT: set([media_player.Commands.EJECT]),
    media_player.Features.OPEN_CLOSE: set([media_player.Commands.OPEN_CLOSE]),
    media_player.Features.AUDIO_TRACK: set([media_player.Commands.AUDIO_TRACK]),
    media_player.Features.SUBTITLE: set([media_player.Commands.SUBTITLE]),
    media_player.Features.RECORD: set(
        [
            media_player.Commands.RECORD,
            media_player.Commands.MY_RECORDINGS,
            media_player.Commands.LIVE,
        ]
    ),
    media_player.Features.SETTINGS: set([media_player.Commands.SETTINGS]),
}


def features_and_commands(
    commands: dict[media_player.Commands | str, MythTVCommand],
) -> Tuple[list[media_player.Features], list[str]]:
    """Map MythTVCommands to UC2 media player features and simple commands."""
    features: list[media_player.Features] = []
    available_commands = {c for c in commands.keys() if isinstance(c, media_player.Commands)}
    simple_commands = commands.copy()  # Do not delete from underlying driver.

    for feature, required_commands in FEATURE_REQUIRED_COMMANDS.items():
        if all(r in available_commands for r in required_commands):
            logging.info("All %d commands required for feature %s present", len(required_commands), feature.name)
            features.append(feature)
            for c in required_commands:
                del simple_commands[c]
        else:
            logging.info(
                "Missing commands needed for feature %s: %s",
                feature.name,
                [e.name for e in required_commands - available_commands],
            )

    return features, list(simple_commands.keys())


async def main():
    """Start the Remote Two integration driver."""
    logging.basicConfig()  # when running on the device: timestamps are added by the journal
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("mythtv").setLevel(level)
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("config").setLevel(level)
    logging.getLogger("root").setLevel(level)

    host = os.getenv("INTG_MYTHTV_HOST", "localhost")
    name = os.getenv("INTG_MYTHTV_NAME", host)
    port = os.getenv("INTG_MYTHTV_PORT", "6544")

    device = config.MythTVDevice(id=name, name=name, address=host, port=port)
    logging.info("Setup: %s", device)

    be = MythTVBackend(device.address, int(device.port))
    mtv = be.frontend(os.getenv("INTG_MYTHTV_FRONTEND_RESTART_COMMAND", None))
    commands = mtv.commands()
    logging.info("MythTV exposes %d commands", len(commands))

    # for c in commands.items():
    #     print(f"C: {c}")

    features, simple_commands = features_and_commands(commands)

    logging.info("Enabling features: %s", [f.name for f in features])
    logging.info("Enabling %d simple commands", len(simple_commands))
    # for f in features:
    #     print(f"F: {f}")
    # for sc in simple_commands:
    #     print(f"SC: {sc}")

    _MYTHTV[device.id] = mtv

    entity = MediaPlayer(
        identifier=device.id,
        name=device.name,
        features=features,
        attributes={},
        options={
            media_player.Options.SIMPLE_COMMANDS: simple_commands,
        },
        cmd_handler=media_player_cmd_handler,
    )

    api.available_entities.add(entity)

    await api.init("driver.json")


def on_exit_signal():
    """Exit after signal recieved."""
    print("got signal: exit")
    _LOOP.stop()


if __name__ == "__main__":
    os.environ["UC_DISABLE_MDNS_PUBLISH"] = "true"  # XXX?

    for signame in ["SIGINT", "SIGTERM"]:
        _LOOP.add_signal_handler(getattr(signal, signame), on_exit_signal)

    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
