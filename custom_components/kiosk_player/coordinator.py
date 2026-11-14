"""Keeps Home Assistant's picture of this relay's screens up to date."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import KioskApi, KioskAuthError, KioskError
from .const import (
    CONF_CREDENTIAL,
    CONF_CREDENTIAL_ID,
    DOMAIN,
    EVENT_COMMAND_UPDATED,
    EVENT_CONNECTION_CHANGED,
    EVENT_PLAYER_OFFLINE,
    EVENT_PLAYER_ONLINE,
    FALLBACK_SCAN_INTERVAL,
)
from .websocket import KioskSocket

_LOGGER = logging.getLogger(__name__)

type Players = dict[int, dict[str, Any]]
type KioskConfigEntry = ConfigEntry[KioskCoordinator]


class KioskCoordinator(DataUpdateCoordinator[Players]):
    """The relay's screens, by id. A full list every minute; the live connection in between."""

    config_entry: KioskConfigEntry

    def __init__(self, hass: HomeAssistant, entry: KioskConfigEntry, api: KioskApi) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=FALLBACK_SCAN_INTERVAL)
        self.api = api
        self.socket = KioskSocket(api, self._handle_message, self._connection_changed, self._auth_failed)
        self.last_message_at = None
        self.server_version: str | None = None
        self.last_commands: list[dict[str, Any]] = []

    async def _async_update_data(self) -> Players:
        try:
            players = await self.api.players()
        except KioskAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KioskError as err:
            raise UpdateFailed(str(err)) from err
        return {p["id"]: p for p in players}

    # ----- the live connection -----

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        self.last_message_at = dt_util.utcnow()
        kind = msg["type"]
        data = dict(self.data or {})
        if kind == "player.updated" and isinstance(msg.get("player"), dict):
            player = msg["player"]
            data[player["id"]] = player
            self.async_set_updated_data(data)
        elif kind in ("player.online", "player.offline"):
            player_id = msg.get("player_id")
            online = kind == "player.online"
            if player_id in data:
                data[player_id] = {**data[player_id], "online": online}
                self.async_set_updated_data(data)
            self.hass.bus.async_fire(
                EVENT_PLAYER_ONLINE if online else EVENT_PLAYER_OFFLINE,
                {
                    "player_id": player_id,
                    "name": (data.get(player_id) or {}).get("name"),
                    "relay_id": self.config_entry.unique_id,
                },
            )
        elif kind == "player.removed":
            if data.pop(msg.get("player_id"), None) is not None:
                self.async_set_updated_data(data)
        elif kind == "command.updated" and isinstance(msg.get("command"), dict):
            command = msg["command"]
            self.last_commands = [command, *[c for c in self.last_commands if c.get("id") != command.get("id")]][:20]
            self.hass.bus.async_fire(EVENT_COMMAND_UPDATED, {**command, "relay_id": self.config_entry.unique_id})
        elif kind == "resync":
            await self.async_request_refresh()
        elif kind == "credential.rotate":
            await self._take_new_credential(msg)
        elif kind in ("relay.disabled", "relay.deleted"):
            _LOGGER.warning("The Kiosk server says this relay was %s", kind.split(".")[1])
        elif kind == "hello":
            # A fresh connection: catch up on anything missed while it was down.
            await self.async_request_refresh()

    async def _take_new_credential(self, msg: dict[str, Any]) -> None:
        credential = msg.get("credential")
        if not isinstance(credential, str) or not credential.startswith("rk_"):
            return
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_CREDENTIAL: credential, CONF_CREDENTIAL_ID: msg.get("credential_id")},
        )
        self.api.credential = credential
        await self.socket.send({"type": "credential.rotated", "credential_id": msg.get("credential_id")})
        _LOGGER.info("Kiosk server handed this relay a new credential")
        # Using the new credential retires the old one (and closes this connection), so reconnect with it.
        await self.socket.reconnect()

    @callback
    def _connection_changed(self, connected: bool) -> None:
        self.hass.bus.async_fire(
            EVENT_CONNECTION_CHANGED, {"connected": connected, "relay_id": self.config_entry.unique_id}
        )
        self.async_update_listeners()

    @callback
    def _auth_failed(self, status: str) -> None:
        self.config_entry.async_start_reauth(self.hass)
