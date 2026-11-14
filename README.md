# Kiosk Player for Home Assistant

Shows the Kiosk Signage screens at this site in Home Assistant, and lets automations change
what they play. It is for a **relay**: a Home Assistant at one of your sites, paired with the
main Kiosk server (the Home Assistant that runs the Kiosk Signage add-on in main mode).

The code is developed in [hybrid87sg/kiosk-player](https://github.com/hybrid87sg/kiosk-player);
this repository holds the published copies for HACS.

## What you get

For each screen this relay controls (a Home Assistant device per screen):

- **Online** (on/off), **Playlist**, **Playing** (the file on screen), **Last seen**
- **Playlist choice**: Automatic, or one of its location's playlists
- **Refresh**: makes the screen fetch its playlist again
- Free storage, app version and any playback problem (diagnostic)

For the relay itself: **Main server connected**, **Screens online**, **Screens offline**.

Actions for automations: `kiosk_player.play_playlist` (playlist: `Automatic`, or a playlist's
name or number) and `kiosk_player.refresh_player`, both aimed at screen devices.

Events: `kiosk_player_player_online`, `kiosk_player_player_offline`,
`kiosk_player_command_updated`, `kiosk_player_connection_changed`.

TVs check in about once a minute, so a change reaches the screen within a minute. The
**command updated** event says when it did (status `acknowledged`).

## Needs

- The main Kiosk server (Kiosk Signage add-on) **0.7.0 or newer**, with the relay set up under
  Settings → Home Assistant Relays. Earlier versions have no relay pairing.
- Home Assistant 2025.1 or newer, and Tailscale (or another private network) between the sites.

## Install

1. In HACS: ⋮ → **Custom repositories** → add `https://github.com/hybrid87sg/kiosk-player-ha`,
   type **Integration**. Then find **Kiosk Player** in HACS and download it. Restart Home Assistant.
2. On the **main** Kiosk server's web page: **Settings → Home Assistant Relays** → **Add relay**
   (or **Pairing code** on an existing one). Note the code: it works once and for 10 minutes.
3. Here: **Settings → Devices & services → Add integration → Kiosk Player**. Enter the main
   server's Tailscale address (e.g. `100.101.102.103`; port 3000 is assumed) and the code.

The same code also pairs this site's Kiosk add-on (relay mode): put it in the add-on's
**Pairing code** option.

## Examples

Evening playlists, a promo button, offline alerts and more:
[docs/ha-examples.md](https://github.com/hybrid87sg/kiosk-player/blob/main/docs/ha-examples.md).

## If the main server stops accepting this relay

If its credential is revoked or the relay is disabled on the main server, Home Assistant shows
**Repair / Reconfigure** for Kiosk Player. Make a new pairing code on the main server and enter it.

## Privacy

The relay's credential is stored like other Home Assistant integration secrets (in `.storage`).
It is never written to logs, and diagnostics downloads leave it and the server's address out.
