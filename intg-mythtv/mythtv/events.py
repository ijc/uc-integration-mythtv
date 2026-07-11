"""
MythTV communication for Remote Two integration.

Event Bus

:copyright: (c) by Ian Campbell
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio

# import functools
from asyncio import AbstractEventLoop
from enum import StrEnum
from typing import Any, Callable

from pyee.asyncio import AsyncIOEventEmitter


class Event(StrEnum):
    """MythTV Events."""

    FRONTEND_DISCOVERED = "frontend_discovered"

    # Something not covered below
    UNKNOWN_SYSTEM_EVENT = "system_event"

    # https://wiki.mythtv.org/wiki/SYSTEM_EVENT_(Myth_Protocol)

    CLIENT_CONNECTED = "CLIENT_CONNECTED"

    CLIENT_DISCONNECTED = "CLIENT_DISCONNECTED"

    SLAVE_CONNECTED = "SLAVE_CONNECTED"

    SLAVE_DISCONNECTED = "SLAVE_DISCONNECTED"

    SCHEDULER_RAN = "SCHEDULER_RAN"

    REC_PENDING = "REC_PENDING"

    REC_STARTED = "REC_STARTED"

    REC_STARTED_WRITING = "REC_STARTED_WRITING"

    REC_FINISHED = "REC_FINISHED"

    REC_DELETED = "REC_DELETED"

    REC_EXPIRED = "REC_EXPIRED"

    LIVE_TV_STARTED = "LIVE_TV_STARTED"

    PLAY_STARTED = "PLAY_STARTED"

    PLAY_STOPPED = "PLAY_STOPPED"

    PLAY_PAUSED = "PLAY_PAUSED"

    PLAY_UNPAUSED = "PLAY_UNPAUSED"

    PLAY_CHANGED = "PLAY_CHANGED"

    MASTER_STARTED = "MASTER_STARTED"

    MASTER_SHUTDOWN = "MASTER_SHUTDOWN"

    NET_CTRL_CONNECTED = "NET_CTRL_CONNECTED"

    NET_CTRL_DISCONNECTED = "NET_CTRL_DISCONNECTED"

    MYTHFILLDATABASE_RAN = "MYTHFILLDATABASE_RAN"

    SETTINGS_CACHE_CLEARED = "SETTINGS_CACHE_CLEARED"

    USER_1 = "USER_1"

    USER_2 = "USER_2"

    USER_3 = "USER_3"

    USER_4 = "USER_4"

    USER_5 = "USER_5"

    USER_6 = "USER_6"

    USER_7 = "USER_7"

    USER_8 = "USER_8"

    USER_9 = "USER_9"

    # Undocuments SYSTEM_EVENT

    SCREEN_TYPE = "SCREEN_TYPE"


class EventBus:
    """MythTV Event Bus."""

    def __init__(self, loop: AbstractEventLoop):
        """
        Create an integration driver API instance.

        :param loop: optional event loop. The currently running event loop is used if
                     not provided.
        """
        self._loop = loop if loop else asyncio.get_event_loop()
        self._events = AsyncIOEventEmitter(self._loop)

    def loop(self) -> AbstractEventLoop:
        """Get the underlying event loop."""
        return self._loop

    def emit(
        self,
        event: Event,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Emit an Event."""
        return self._events.emit(event, *args, **kwargs)

    def on(self, event: Event) -> Callable[[Callable], Callable]:
        """Register a listener for an Event."""

        def on(f: Callable) -> Callable:
            self._events.add_listener(event, f)
            return f

        return on
