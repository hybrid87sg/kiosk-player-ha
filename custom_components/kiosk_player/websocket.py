"""The live connection to the Kiosk server (/api/relay/v1/ws).

It stays open while the integration runs. The server sends news about this relay's
screens as it happens; this side answers "ping" with "pong". When the connection
drops it is opened again, waiting 1 s, then 2 s, 4 s ... up to 60 s (with some
randomness so many relays don't all retry at once). A reconnect asks for what it
missed with ?after=<last event number>.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import random
from typing import Any

import aiohttp

from .api import KioskApi

_LOGGER = logging.getLogger(__name__)

BACKOFF_START = 1.0
BACKOFF_MAX = 60.0
# The server pings every 25 s; nothing at all for this long means the line is dead.
RECEIVE_TIMEOUT = 75.0


class KioskSocket:
    """Keeps one live connection open and hands each message to on_message."""

    def __init__(
        self,
        api: KioskApi,
        on_message: Callable[[dict[str, Any]], Awaitable[None]],
        on_connection: Callable[[bool], None],
        on_auth_failed: Callable[[str], None],
    ) -> None:
        self.api = api
        self._on_message = on_message
        self._on_connection = on_connection
        self._on_auth_failed = on_auth_failed
        self.last_event: int | None = None
        self.connected = False
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._stopped = False
        self._reconnect_now = asyncio.Event()

    async def run(self) -> None:
        """Connects, reads, reconnects. Returns only when stopped or the credential is refused."""
        delay = BACKOFF_START
        while not self._stopped:
            try:
                async with self.api.session.ws_connect(
                    self.api.websocket_url(self.last_event),
                    headers={"Authorization": f"Bearer {self.api.credential}"},
                    heartbeat=None,
                    timeout=aiohttp.ClientWSTimeout(ws_receive=RECEIVE_TIMEOUT),
                ) as ws:
                    self._ws = ws
                    self._set_connected(True)
                    delay = BACKOFF_START
                    await self._read(ws)
            except aiohttp.WSServerHandshakeError as err:
                if err.status in (401, 403):
                    self._set_connected(False)
                    _LOGGER.warning("The Kiosk server refused this relay's credential (%s)", err.status)
                    self._on_auth_failed(str(err.status))
                    return
                _LOGGER.debug("Kiosk live connection refused: %s", err.status)
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.debug("Kiosk live connection lost: %s", err)
            finally:
                self._ws = None
            self._set_connected(False)
            if self._stopped:
                return
            if self._reconnect_now.is_set():
                self._reconnect_now.clear()
                continue
            wait = min(BACKOFF_MAX, delay) * random.uniform(0.8, 1.2)
            delay = min(BACKOFF_MAX, delay * 2)
            try:
                await asyncio.wait_for(self._reconnect_now.wait(), timeout=wait)
                self._reconnect_now.clear()
            except TimeoutError:
                pass

    async def _read(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        async for message in ws:
            if message.type is not aiohttp.WSMsgType.TEXT:
                break
            try:
                data = message.json()
            except ValueError:
                continue
            if not isinstance(data, dict) or not isinstance(data.get("type"), str):
                continue
            if isinstance(data.get("event"), int):
                self.last_event = data["event"]
            if data["type"] == "hello" and self.last_event is None:
                self.last_event = data.get("last_event")
            if data["type"] == "ping":
                await ws.send_json({"type": "pong"})
                continue
            await self._on_message(data)

    async def send(self, data: dict[str, Any]) -> None:
        if self._ws is not None and not self._ws.closed:
            await self._ws.send_json(data)

    async def reconnect(self) -> None:
        """Closes the connection and opens it again straight away (e.g. with a new credential)."""
        self._reconnect_now.set()
        if self._ws is not None:
            await self._ws.close()

    async def stop(self) -> None:
        self._stopped = True
        self._reconnect_now.set()
        if self._ws is not None:
            await self._ws.close()

    def _set_connected(self, value: bool) -> None:
        if value != self.connected:
            self.connected = value
            self._on_connection(value)
