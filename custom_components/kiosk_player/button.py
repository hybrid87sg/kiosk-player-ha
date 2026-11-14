"""Button: make a screen fetch its playlist again."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import KioskConfigEntry, KioskCoordinator
from .entity import KioskPlayerEntity, add_player_entities
from .services import run_command


async def async_setup_entry(
    hass: HomeAssistant, entry: KioskConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    add_player_entities(entry, async_add_entities, lambda c, player_id: [RefreshButton(c, player_id)])


class RefreshButton(KioskPlayerEntity, ButtonEntity):
    def __init__(self, coordinator: KioskCoordinator, player_id: int) -> None:
        super().__init__(coordinator, player_id, "refresh")

    async def async_press(self) -> None:
        await run_command(self.coordinator, self.player_id, "refresh")
