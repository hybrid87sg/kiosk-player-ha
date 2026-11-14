"""Constants for the Kiosk Player integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "kiosk_player"

CONF_CREDENTIAL = "credential"
CONF_CREDENTIAL_ID = "credential_id"
CONF_PAIRING_CODE = "pairing_code"
CONF_RELAY_ID = "relay_id"
CONF_RELAY_NAME = "relay_name"
CONF_SITE = "site"

# The Kiosk server listens on this port; an address typed without one gets it.
DEFAULT_PORT = 3000

# The live connection brings changes as they happen; a full refresh this often is the fallback.
FALLBACK_SCAN_INTERVAL = timedelta(seconds=60)

# What a playlist picker shows for "follow the location's Landscape/Portrait playlist".
AUTOMATIC = "Automatic"

# Events automations can trigger on.
EVENT_PLAYER_ONLINE = f"{DOMAIN}_player_online"
EVENT_PLAYER_OFFLINE = f"{DOMAIN}_player_offline"
EVENT_COMMAND_UPDATED = f"{DOMAIN}_command_updated"
EVENT_CONNECTION_CHANGED = f"{DOMAIN}_connection_changed"

SERVICE_PLAY_PLAYLIST = "play_playlist"
SERVICE_REFRESH_PLAYER = "refresh_player"
ATTR_PLAYLIST = "playlist"
