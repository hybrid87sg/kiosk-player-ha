"""Kiosk Player: this site's Kiosk screens in Home Assistant.

Paired with the main Kiosk server as one relay, it shows the relay's screens as devices
(online, playlist, file playing, ...), lets automations change a screen's playlist or
make it refresh, and listens on a live connection so changes show up at once.
"""

from __future__ import annotations

import contextlib

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import KioskApi, KioskError
from .const import CONF_CREDENTIAL, DOMAIN
from .coordinator import KioskConfigEntry, KioskCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SELECT, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KioskConfigEntry) -> bool:
    api = KioskApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_CREDENTIAL])
    coordinator = KioskCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    with contextlib.suppress(KioskError):  # the version is only shown on the relay's device page
        coordinator.server_version = (await api.me()).get("server", {}).get("version")
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, coordinator.socket.run(), f"{DOMAIN} live connection")
    entry.async_on_unload(coordinator.socket.stop)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KioskConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: KioskConfigEntry, device: dr.DeviceEntry
) -> bool:
    """A screen's device can be deleted once it's no longer this relay's (the relay itself can't)."""
    coordinator = entry.runtime_data
    for domain, identifier in device.identifiers:
        if domain != DOMAIN:
            continue
        if identifier == entry.unique_id:
            return False
        player_id = identifier.rsplit("_", 1)[-1]
        if player_id.isdigit() and int(player_id) in (coordinator.data or {}):
            return False
    return True
