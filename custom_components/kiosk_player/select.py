"""Select: which playlist a screen plays (Automatic, or one of its location's playlists)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AUTOMATIC
from .coordinator import KioskConfigEntry, KioskCoordinator
from .entity import KioskPlayerEntity, add_player_entities
from .services import playlist_labels, playlist_payload, run_command


async def async_setup_entry(
    hass: HomeAssistant, entry: KioskConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    add_player_entities(entry, async_add_entities, lambda c, player_id: [PlaylistSelect(c, player_id)])


class PlaylistSelect(KioskPlayerEntity, SelectEntity):
    def __init__(self, coordinator: KioskCoordinator, player_id: int) -> None:
        super().__init__(coordinator, player_id, "playlist_select")

    @property
    def options(self) -> list[str]:
        return [AUTOMATIC, *playlist_labels(self.player or {})]

    @property
    def current_option(self) -> str | None:
        player = self.player
        if not player:
            return None
        if player.get("playlist_auto"):
            return AUTOMATIC
        for label, playlist_id in playlist_labels(player).items():
            if playlist_id == player.get("playlist_id"):
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        payload = playlist_payload(self.player or {}, option)
        await run_command(self.coordinator, self.player_id, "play_playlist", payload)
