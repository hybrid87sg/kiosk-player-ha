"""Diagnostics download: enough to help with a problem, never the credential or the server address."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .const import CONF_CREDENTIAL, CONF_CREDENTIAL_ID
from .coordinator import KioskConfigEntry

REDACT = {CONF_CREDENTIAL, CONF_CREDENTIAL_ID, CONF_URL}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: KioskConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    players = list((coordinator.data or {}).values())
    return {
        "entry": async_redact_data(dict(entry.data), REDACT),
        "connected": coordinator.socket.connected,
        "last_event": coordinator.socket.last_event,
        "last_message_at": coordinator.last_message_at.isoformat() if coordinator.last_message_at else None,
        "last_update_success": coordinator.last_update_success,
        "players": [
            {
                k: p.get(k)
                for k in ("id", "online", "playlist_auto", "playing_playlist_id", "app_version", "model", "open_now")
            }
            for p in players
        ],
        "last_commands": [
            {k: c.get(k) for k in ("id", "player_id", "kind", "status", "created_at")}
            for c in coordinator.last_commands
        ],
    }
