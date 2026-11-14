"""Actions for automations: kiosk_player.play_playlist and kiosk_player.refresh_player.

Both take screens as targets (their Home Assistant devices). The main server checks
that each screen belongs to this relay; one that doesn't is a clear error, not a guess.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from .api import KioskAuthError, KioskError, KioskNotFound, KioskRejected
from .const import ATTR_PLAYLIST, AUTOMATIC, DOMAIN, SERVICE_PLAY_PLAYLIST, SERVICE_REFRESH_PLAYER
from .coordinator import KioskCoordinator

TARGET = {vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}
PLAY_SCHEMA = vol.Schema({**TARGET, vol.Required(ATTR_PLAYLIST): vol.Any(cv.positive_int, cv.string)})
REFRESH_SCHEMA = vol.Schema(TARGET)


def playlist_labels(player: dict[str, Any]) -> dict[str, int]:
    """Option label -> playlist id. Two playlists with the same name are told apart by id."""
    names = [p["name"] for p in player.get("playlists") or []]
    labels: dict[str, int] = {}
    for p in player.get("playlists") or []:
        label = p["name"] if names.count(p["name"]) == 1 and p["name"] != AUTOMATIC else f"{p['name']} (#{p['id']})"
        labels[label] = p["id"]
    return labels


def playlist_payload(player: dict[str, Any], choice: str | int) -> dict[str, Any]:
    """'Automatic', a playlist's name, a select option like 'Promo (#7)', or its id -> command payload."""
    if isinstance(choice, str) and choice.strip().lower() == AUTOMATIC.lower():
        return {"automatic": True}
    playlists = player.get("playlists") or []
    if isinstance(choice, int) or (isinstance(choice, str) and choice.strip().isdigit()):
        return {"playlist_id": int(choice)}
    labels = playlist_labels(player)
    if choice in labels:
        return {"playlist_id": labels[choice]}
    matches = [p for p in playlists if p["name"].casefold() == str(choice).strip().casefold()]
    if len(matches) == 1:
        return {"playlist_id": matches[0]["id"]}
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="unknown_playlist" if not matches else "ambiguous_playlist",
        translation_placeholders={"playlist": str(choice), "player": player.get("name") or "this screen"},
    )


async def run_command(
    coordinator: KioskCoordinator, player_id: int, kind: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Sends one command and turns the server's answer into a Home Assistant error if needed."""
    name = (coordinator.data or {}).get(player_id, {}).get("name") or f"screen {player_id}"
    try:
        result = await coordinator.api.command(player_id, kind, payload)
    except KioskNotFound as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="not_this_relays", translation_placeholders={"player": name}
        ) from err
    except KioskRejected as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_rejected",
            translation_placeholders={"player": name, "reason": str(err)},
        ) from err
    except KioskAuthError as err:
        coordinator.config_entry.async_start_reauth(coordinator.hass)
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="auth_failed") from err
    except KioskError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="server_error", translation_placeholders={"reason": str(err)}
        ) from err
    await coordinator.async_request_refresh()
    return result


def _targets(hass: HomeAssistant, call: ServiceCall) -> list[tuple[KioskCoordinator, int]]:
    registry = dr.async_get(hass)
    found: list[tuple[KioskCoordinator, int]] = []
    for device_id in call.data[ATTR_DEVICE_ID]:
        device = registry.async_get(device_id)
        target = None
        if device is not None:
            for entry_id in device.config_entries:
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
                    continue
                for domain, identifier in device.identifiers:
                    prefix = f"{entry.unique_id}_"
                    if domain == DOMAIN and identifier.startswith(prefix) and identifier[len(prefix) :].isdigit():
                        target = (entry.runtime_data, int(identifier[len(prefix) :]))
        if target is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_a_screen",
                translation_placeholders={"device": device_id},
            )
        found.append(target)
    return found


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def play_playlist(call: ServiceCall) -> None:
        targets = _targets(hass, call)
        # Check every choice first, so a typo doesn't leave half the screens changed.
        planned = [
            (
                coordinator,
                player_id,
                playlist_payload((coordinator.data or {}).get(player_id, {}), call.data[ATTR_PLAYLIST]),
            )
            for coordinator, player_id in targets
        ]
        for coordinator, player_id, payload in planned:
            await run_command(coordinator, player_id, "play_playlist", payload)

    async def refresh_player(call: ServiceCall) -> None:
        for coordinator, player_id in _targets(hass, call):
            await run_command(coordinator, player_id, "refresh")

    hass.services.async_register(DOMAIN, SERVICE_PLAY_PLAYLIST, play_playlist, schema=PLAY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_PLAYER, refresh_player, schema=REFRESH_SCHEMA)
