#!/usr/bin/env python3
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
from typing import Any

import config
import mythtv
import ucapi
from mythtv import MythTV
from ucapi import Remote, remote
from ucapi.ui import Buttons, Size, UiPage, create_btn_mapping, create_ui_text

_LOG = logging.getLogger("driver")  # avoid having __main__ in log messages
_LOOP = asyncio.get_event_loop()

# Global variables
api = ucapi.IntegrationAPI(_LOOP)
_mythtv: mythtv.MythTV = None


@api.listens_to(ucapi.Events.CONNECT)
async def on_connect():
    """When the UCR2 connects, all configured MythTV frontends are getting connected."""
    await api.set_device_state(ucapi.DeviceStates.CONNECTED)  # just to make sure the device state is set


async def remote_cmd_handler(entity: ucapi.Remote, cmd_id: str, params: dict[str, Any] | None) -> ucapi.StatusCodes:
    """
    Remote command handler.

    Called by the integration-API if a command is sent to a configured remote-entity.

    :param entity: remote entity
    :param cmd_id: command
    :param params: optional command parameters
    :return: status of the command
    """
    print(f"Got {entity.id} command request: {cmd_id}")

    _LOG.info("command: %s %s", cmd_id, params if params else "")

    match cmd_id:
        case remote.Commands.SEND_CMD:
            command = params.get("command")
            # It's up to the integration what to do with an unknown command.
            # If the supported commands are provided as simple_commands, then it's
            # easy to validate.
            # if command not in supported_commands:
            #     print(f"Unknown command: {command}", file=sys.stderr)
            #     return ucapi.StatusCodes.BAD_REQUEST

            # repeat = params.get("repeat", 1)
            # delay = params.get("delay", 0)
            # hold = params.get("hold", 0)

            if not _mythtv.run_command(command):
                _LOG.error("command: %s failed", cmd_id)
                return ucapi.StatusCodes.BAD_REQUEST

        # case remote.Commands.SEND_CMD_SEQUENCE:
        #     sequence = params.get("sequence")
        #     repeat = params.get("repeat", 1)
        #     delay = params.get("delay", 0)
        #     hold = params.get("hold", 0)
        #     print(
        #         f"Command sequence: {sequence} (repeat={repeat}, delay={delay}, hold={hold})"
        #     )
        case _:
            _LOG.warning("Unsupported command: %s", cmd_id)
            return ucapi.StatusCodes.BAD_REQUEST

    return ucapi.StatusCodes.OK


def create_ui_pages(commands):
    """Create the UI pages for the given map of commands."""
    ui_pages = []
    ui_page = None
    for cmd, info in commands.items():
        if ui_page is None or len(ui_page.items) == 6:
            ui_page = UiPage(f"page{len(ui_pages)}", f"Page {len(ui_pages)}", grid=Size(1, 6))
            ui_pages.append(ui_page)

        ui_page.add(create_ui_text(info.desc, 0, len(ui_page.items), cmd=cmd))
    return ui_pages


def create_button_mapping(commands):
    """Create button mapping for given map of commands."""
    button_mapping = []
    for btn, short_cmd, long_cmd in [
        (Buttons.BACK, "ESCAPE", None),
        (Buttons.HOME, "Main Menu", None),
        # (Buttons.VOICE, "", None),
        (Buttons.VOLUME_UP, "VOLUMEUP", None),
        (Buttons.VOLUME_DOWN, "VOLUMEDOWN", None),
        (Buttons.MUTE, "MUTE", None),
        (Buttons.DPAD_UP, "UP", None),
        (Buttons.DPAD_DOWN, "DOWN", None),
        (Buttons.DPAD_LEFT, "LEFT", None),
        (Buttons.DPAD_RIGHT, "RIGHT", None),
        (Buttons.DPAD_MIDDLE, "SELECT", None),
        (Buttons.GREEN, "MENUGREEN", None),
        (Buttons.YELLOW, "MENUYELLOW", None),
        (Buttons.RED, "MENURED", None),
        (Buttons.BLUE, "MENUBLUE", None),
        (Buttons.CHANNEL_UP, "CHANNELUP", None),
        (Buttons.CHANNEL_DOWN, "CHANNELDOWN", None),
        (Buttons.PREV, "SEEKRWND", "PREVTRACK"),
        (Buttons.PLAY, "PLAY", None),
        (Buttons.NEXT, "SEEKFFWD", "NEXTRACK"),
        # (Buttons.POWER, "", None),
    ]:
        short_cmd = mythtv.map_action_name_to_uc_simple_command(short_cmd)
        if short_cmd in commands:
            if long_cmd is not None:
                long_cmd = mythtv.map_action_name_to_uc_simple_command(long_cmd)
                if long_cmd not in commands:
                    long_cmd = None
            btn = create_btn_mapping(btn, short_cmd, long_cmd)
            button_mapping.append(btn)

    return button_mapping


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

    host = os.getenv("INTG_MYTHTV_HOST", "localhost")
    name = os.getenv("INTG_MYTHTV_NAME", host)
    port = os.getenv("INTG_MYTHTV_PORT", "6547")

    device = config.MythTVDevice(id=name, name=name, address=host, port=port)
    logging.info("Setup: %s", device)

    mtv = MythTV(device.address, int(device.port))
    commands = mtv.commands()

    cmds = list(commands.keys())

    ui_pages = create_ui_pages(commands)
    button_mapping = create_button_mapping(commands)

    entity = Remote(
        identifier=device.id,
        name=device.name,
        features=[
            # remote.Features.SEND_CMD,
        ],
        attributes={},
        button_mapping=button_mapping,
        ui_pages=ui_pages,
        simple_commands=cmds,
        cmd_handler=remote_cmd_handler,
    )
    api.available_entities.add(entity)

    global _mythtv
    _mythtv = mtv

    await api.init("driver.json")


def on_exit_signal():
    """Exit after signal recieved."""
    print("got signal: exit")
    _LOOP.stop()


if __name__ == "__main__":
    os.environ["UC_DISABLE_MDNS_PUBLISH"] = "true"

    for signame in ["SIGINT", "SIGTERM"]:
        _LOOP.add_signal_handler(getattr(signal, signame), on_exit_signal)

    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
