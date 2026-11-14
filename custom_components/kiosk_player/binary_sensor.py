"""Binary sensors: is each screen online, and is the relay connected to the main server."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import KioskConfigEntry, KioskCoordinator
from .entity import KioskPlayerEntity, KioskRelayEntity, add_player_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: KioskConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([RelayConnected(entry.runtime_data)])
    add_player_entities(entry, async_add_entities, lambda c, player_id: [PlayerOnline(c, player_id)])


class PlayerOnline(KioskPlayerEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: KioskCoordinator, player_id: int) -> None:
        super().__init__(coordinator, player_id, "online")

    @property
    def is_on(self) -> bool | None:
        return bool(self.player.get("online")) if self.player else None


class RelayConnected(KioskRelayEntity, BinarySensorEntity):
    """On while the live connection to the main Kiosk server is open."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: KioskCoordinator) -> None:
        super().__init__(coordinator, "server_connected")

    @property
    def available(self) -> bool:
        return True  # "not connected" is itself the answer

    @property
    def is_on(self) -> bool:
        return self.coordinator.socket.connected
