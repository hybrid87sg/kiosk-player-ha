"""Shared parts of every Kiosk Player entity: one device per screen, one for the relay."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_RELAY_NAME, DOMAIN
from .coordinator import KioskConfigEntry, KioskCoordinator


def player_identifier(relay_id: str, player_id: int) -> str:
    return f"{relay_id}_{player_id}"


def relay_device_info(entry: KioskConfigEntry) -> DeviceInfo:
    coordinator = entry.runtime_data
    return DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id)},
        name=entry.data.get(CONF_RELAY_NAME) or "Kiosk relay",
        manufacturer="Kiosk Signage",
        model="Relay",
        sw_version=coordinator.server_version,
    )


class KioskRelayEntity(CoordinatorEntity[KioskCoordinator]):
    """An entity about the relay as a whole."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KioskCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = relay_device_info(entry)


class KioskPlayerEntity(CoordinatorEntity[KioskCoordinator]):
    """An entity about one screen."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KioskCoordinator, player_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.player_id = player_id
        relay_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{player_identifier(relay_id, player_id)}_{key}"
        self._attr_translation_key = key
        player = self.player or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player_identifier(relay_id, player_id))},
            name=player.get("name") or f"Screen {player_id}",
            manufacturer="Kiosk Signage",
            model=player.get("model") or "Kiosk Player TV",
            sw_version=player.get("app_version"),
            suggested_area=player.get("location"),
            via_device=(DOMAIN, relay_id),
        )

    @property
    def player(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self.player_id)

    @property
    def available(self) -> bool:
        # A screen that is no longer this relay's (moved or removed) goes unavailable.
        return super().available and self.player is not None


def add_player_entities(
    entry: KioskConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    make: Callable[[KioskCoordinator, int], Iterable[Entity]],
) -> None:
    """Adds entities for every screen now, and for screens that turn up later."""
    coordinator = entry.runtime_data
    added: set[int] = set()

    @callback
    def check() -> None:
        new = set(coordinator.data or {}) - added
        if not new:
            return
        added.update(new)
        async_add_entities([entity for player_id in sorted(new) for entity in make(coordinator, player_id)])

    check()
    entry.async_on_unload(coordinator.async_add_listener(check))
