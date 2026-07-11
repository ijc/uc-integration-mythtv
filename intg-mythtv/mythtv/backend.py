"""
MythTV communication for Remote Two integration.

Using Backend APIs

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
import re
from collections.abc import Callable
from typing import Any, ItemsView

from MythTV import BECache
from MythTV.connections import BEEventConnection
from MythTV.services_api.send import Send

from .events import Event, EventBus
from .frontend import MythTVFrontend


class SystemEventMonitor(BECache):
    """Bridge from Myth BEEventMontor to callback."""

    _cb: Callable[[str, dict[str, str | None]], None]

    def __init__(self, backend: str, cb: Callable[[str, dict[str, str | None]], None]):
        """Create system event monitor for backend."""
        self._cb = cb
        self._log = logging.getLogger(f"{__name__}.{backend}.event_monitor")
        super().__init__(backend=backend, blockshutdown=False, events=True, db=None)

    def _listhandlers(self):
        return [self.event]

    def _neweventconn(self):
        beconn = BEEventConnection(
            backend=self.host,
            port=self.port,
            localname=self.db.gethostname(),
            level=3,  # system events only
        )

        # Until https://github.com/MythTV/mythtv/pull/1409 is merged/released
        old_reconnect = beconn.reconnect

        # cd23715783f3 ("Add IPv6 support to the Python Bindings.")
        # Previous protoype:
        #   def reconnect(self, force=False, hard=False):
        # New prototype:
        #   def reconnect(self, hard=False):
        # Remaning incorrect caller is
        #   self.reconnect(True, True)
        def reconnect(xself, a=False, b=None):
            self._log.debug("Monkey patched BEEventConnect.reconnect called self=%s a=%s b=%s", xself, a, b)
            if b is not None:
                assert a == b
            return old_reconnect(a)

        # pylint: disable=no-value-for-parameter
        beconn.reconnect = reconnect.__get__(self, BEEventConnection)

        return beconn

    # pylint: disable=too-many-return-statements
    def event(self, event=None):
        """Handle an event."""
        if event is None:
            return re.compile("BACKEND_MESSAGE")

        args = event.split("[]:[]")
        if not args:
            self._log.error("Failed to parse BACKEND_MESSAGE: %s", event)
            return None
        message_type, *args = args
        if message_type != "BACKEND_MESSAGE":
            self._log.error("Event is not a BACKEND_MESSAGE: %s", event)
            return None
        if len(args) != 2:
            self._log.error("BACKEND_MESSAGE event has incorrect number args: %s", event)
            return None
        if args[1] != "empty":
            self._log.error("BACKEND_MESSAGE event has incorrect args[1]: %s", event)
            return None

        system_event, event_name, *event_args = args[0].split(" ")
        if system_event != "SYSTEM_EVENT":
            self._log.error("BACKEND_MESSAGE is not a system event: %s", event)
            return None

        event_args_kvp = dict(zip([k.lower() for k in event_args[::2]], event_args[1::2]))

        self._cb(event_name, event_args_kvp)
        return None


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
        self._log = logging.getLogger(f"{__name__}.{host}")
        self._events = events

        if self._events:
            self._loop = self._events.loop()
            self._event_mon = SystemEventMonitor(cb=self._system_event_thread_safe, backend=host)

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

    def _system_event_thread_safe(self, event_name: str, event_args: dict[str, str | None]):
        self._loop.call_soon_threadsafe(self._system_event, event_name, event_args)

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
