"""
MythTV communication for Remote Two integration.

Using Backend APIs

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from asyncio import AbstractEventLoop
from collections.abc import Callable
from itertools import chain, repeat
from typing import Any, ItemsView

from MythTV.connections import BEConnection
from MythTV.exceptions import MythBEError, MythError
from MythTV.services_api.send import Send

from .events import Event, EventBus
from .frontend import MythTVFrontend


class SystemEventMonitor(BEConnection):
    """Bridge from Myth BEEventMontor to callback."""

    _cb: Callable[[str, dict[str, str | None]], None]
    _loop: AbstractEventLoop

    def __init__(
        self,
        parent_logger: logging.Logger,
        backend: str,
        port: int,
        loop: AbstractEventLoop,
        cb: Callable[[str, dict[str, str | None]], None],
    ):
        """Create system event monitor for backend."""
        self._cb = cb
        self._loop = loop
        self._log = parent_logger.getChild("event_monitor")

        super().__init__(backend=backend, port=port, blockshutdown=False)

        self._loop.add_reader(self.socket, self._event_handler)

    def announce(self):
        """Announce to backend as a monitor for system events."""
        # set event level, 3=system only, 2=generic only, 1=both, 0=none
        res = self.backendCommand(f"ANN Monitor {self.localname} 3")
        print(f"ANNOUNCE: Result={res}")
        if res != "OK":
            raise MythBEError(MythError.PROTO_ANNOUNCE, self.host, self.port, res)

    def reconnect_with_retries(self, hard=False, timeouts=None):
        """Reconnect with retries, sleeping asynchronously."""
        self._log.info("SystemEventMonitor.reconnect_with_retries [%s]:%d hard=%s", self.host, self.port, hard)
        if not timeouts:
            # ~33s in total
            # timeouts = enumerate([1, 1, 2, 3, 5, 8, 13], 1)
            # Forever
            timeouts = enumerate(chain([1, 1, 2, 3], repeat(5)), 1)

        try:
            nr, next_delay = next(timeouts)
        except StopIteration as exc:
            self._log.error("Too many retries reconnecting to [%s]:%d", self.host, self.port)
            raise MythBEError(MythError.PROTO_CONNECTION, self.host, self.port) from exc
        try:
            self._log.info("Reconnect attempt %d", nr)
            self.reconnect(hard)
            self._log.info("Reconnected successfully")
            self._loop.add_reader(self.socket, self._event_handler)
        except (MythError, OSError) as e:
            self._log.info("Error connecting [%s]:%d: %s", self.host, self.port, e)
            self._log.info("Retrying in %ds", next_delay)
            self._loop.call_later(next_delay, self.reconnect_with_retries, True, timeouts)

    # pylint: disable=too-many-return-statements
    def _event_handler(self):
        """Handle socket becoming readable."""
        try:
            event = self.socket.recvheader(deadline=0.0)
        except MythError as exc:
            self._loop.remove_reader(self.socket)
            if exc.sockcode == 54:
                print(f"Reconnecting after error: {exc}")
                self._loop.call_soon(self.reconnect_with_retries, True)
                return

            self._log.error("FATAL error: %s", exc)
            raise exc

        try:
            args = str(event, "utf-8").split("[]:[]")
        except UnicodeDecodeError:
            self._log.error("Invalid UTF-8 event: %s", event)
            return

        if not args:
            self._log.error("Failed to parse BACKEND_MESSAGE: %s", event)
            return
        message_type, *args = args
        if message_type != "BACKEND_MESSAGE":
            self._log.info("Event is not a BACKEND_MESSAGE: %s", event)
            return
        if len(args) != 2:
            self._log.error("BACKEND_MESSAGE event has incorrect number args: %s", event)
            return
        if args[1] != "empty":
            self._log.error("BACKEND_MESSAGE event has incorrect args[1]: %s", event)
            return

        system_event, event_name, *event_args = args[0].split(" ")
        if system_event != "SYSTEM_EVENT":
            self._log.error("BACKEND_MESSAGE is not a system event: %s", event)
            return

        event_args_kvp = dict(zip([k.lower() for k in event_args[::2]], event_args[1::2]))

        self._cb(event_name, event_args_kvp)


class MythTVBackend(Send):
    """API calls to MythTV backend."""

    _frontends: dict[str, MythTVFrontend]
    _frontend_restart_commands: dict[str, str]

    def __init__(
        self,
        host: str,
        port: int = 6544,
        frontend_restart_commands: dict[str, str] | None = None,
        events: EventBus | None = None,
    ):
        """Initialize the object."""
        super().__init__(host=host, port=port)
        self._log = logging.getLogger(__name__).getChild(host.split(".", 1)[0])
        self._events = events

        if self._events:
            self._loop = self._events.loop()
            self._event_mon = SystemEventMonitor(
                parent_logger=self._log, backend=host, port=6543, loop=self._loop, cb=self._system_event
            )

        self._frontend_restart_commands = frontend_restart_commands if frontend_restart_commands else {}

        self._frontends = {}
        for f in self._get_frontends_from_backend():
            self._add_frontend(f)

    def _get_frontends_from_backend(self) -> list[Any]:
        try:
            return self.send("Status/GetBackendStatus")["BackendStatus"]["Frontends"]
        except (RuntimeError, RuntimeWarning) as e:
            self._log.error("Status/GetBackendStatus: %s", e)
            return []

    def _add_frontend(self, f):
        name = f["Name"].lower()
        if not f["OnLine"]:
            self._log.info("Skipping offline Frontend: %s", name)
            return

        if name in self._frontends:
            self._log.error("Duplicated frontend! %s", name)
            return

        self._log.info("Adding Frontend: %s", name)

        restart_cmd = self._frontend_restart_commands.get(name, None)
        frontend = MythTVFrontend(
            backend=self,
            name=name,
            host=f["IP"],
            port=f["Port"],
            frontend_restart_command=restart_cmd,
        )
        self._frontends[name] = frontend

        self._emit(Event.FRONTEND_DISCOVERED, name=name, frontend=frontend)

    def frontends(self) -> ItemsView[str, MythTVFrontend]:
        """Get all frontends. Name mappping to MythTVFrontend object."""
        return self._frontends.items()

    def _emit(
        self,
        event: Event,
        *args: Any,
        **kwargs: Any,
    ):
        if self._events:
            self._events.emit(event, *args, **kwargs)

    def _system_event(self, event_name: str, event_args: dict[str, str | None]):
        if "chanid" in event_args and "starttime" in event_args:
            jsondata = {
                "ChanId": event_args["chanid"],
                "StartTime": event_args["starttime"],
            }
            try:
                program = self.send("Dvr/GetRecorded", jsondata=jsondata)["Program"]
                event_args["program"] = program
            except (RuntimeError, RuntimeWarning) as e:
                # e.g. video playback input is:
                #    {'hostname': 'iranon', 'chanid': '0', 'starttime': '2026-07-12T17:08:35Z', 'sender': 'iranon'}
                # which are not valid arguments.
                self._log.error("Dvr/GetRecorded failed: %s", e)
                self._log.debug(event_args)
                event_args["program"] = None

        if (
            event_name == "CLIENT_CONNECTED"
            and event_args["hostname"]
            and event_args["hostname"].lower() not in self._frontends
        ):
            self._log.info("CLIENT_CONNECTED for unknown hostname %s", event_args["hostname"])
            frontend = [f for f in self._get_frontends_from_backend() if f["Name"] == event_args["hostname"]]
            if len(frontend) != 1:
                self._log.debug("CLIENT %s not a frontend", event_args["hostname"])
            else:
                self._add_frontend(frontend[0])

        try:
            self._emit(Event(event_name), **event_args)
        except ValueError:
            self._emit(Event.UNKNOWN_SYSTEM_EVENT, event_name=event_name, **event_args)

    def get_image_url(self, chanid: str, starttime: str) -> str:
        """Get backend URL for preview image."""
        # Same as Send.send
        self.endpoint = "Content/GetPreviewImage"
        self.postdata = None
        self.jsondata = None
        self.rest = f"ChanId={chanid}&StartTime={starttime}&Width=360"
        self.opts = None

        self._set_missing_opts()

        return self._form_url()
