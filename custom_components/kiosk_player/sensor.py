"""Sensors: what each screen is doing, and how the relay is connected."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import KioskConfigEntry, KioskCoordinator
from .entity import KioskPlayerEntity, KioskRelayEntity, add_player_entities


def _timestamp(ms: Any) -> datetime | None:
    return dt_util.utc_from_timestamp(ms / 1000) if isinstance(ms, int | float) else None


@dataclass(frozen=True, kw_only=True)
class PlayerSensorDescription(SensorEntityDescription):
    value: Callable[[dict[str, Any]], Any]


PLAYER_SENSORS: tuple[PlayerSensorDescription, ...] = (
    PlayerSensorDescription(key="playlist", value=lambda p: p.get("playlist_name")),
    PlayerSensorDescription(key="current_file", value=lambda p: p.get("current_filename")),
    PlayerSensorDescription(
        key="last_seen", device_class=SensorDeviceClass.TIMESTAMP, value=lambda p: _timestamp(p.get("last_seen"))
    ),
    PlayerSensorDescription(
        key="free_storage",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda p: p.get("free_bytes"),
    ),
    PlayerSensorDescription(
        key="app_version", entity_category=EntityCategory.DIAGNOSTIC, value=lambda p: p.get("app_version")
    ),
    PlayerSensorDescription(
        key="playback_error", entity_category=EntityCategory.DIAGNOSTIC, value=lambda p: p.get("playback_error")
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: KioskConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            RelayCountSensor(coordinator, "players_online", True),
            RelayCountSensor(coordinator, "players_offline", False),
            RelayLastMessageSensor(coordinator),
        ]
    )
    add_player_entities(
        entry,
        async_add_entities,
        lambda c, player_id: [PlayerSensor(c, player_id, d) for d in PLAYER_SENSORS],
    )


class PlayerSensor(KioskPlayerEntity, SensorEntity):
    entity_description: PlayerSensorDescription

    def __init__(self, coordinator: KioskCoordinator, player_id: int, description: PlayerSensorDescription) -> None:
        super().__init__(coordinator, player_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.player) if self.player else None


class RelayCountSensor(KioskRelayEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: KioskCoordinator, key: str, online: bool) -> None:
        super().__init__(coordinator, key)
        self._online = online

    @property
    def native_value(self) -> int:
        return sum(1 for p in (self.coordinator.data or {}).values() if bool(p.get("online")) == self._online)


class RelayLastMessageSensor(KioskRelayEntity, SensorEntity):
    """When the main server last sent this relay anything on the live connection."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KioskCoordinator) -> None:
        super().__init__(coordinator, "last_message")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_message_at
