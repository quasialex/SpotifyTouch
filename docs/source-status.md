# Consolidated source status

The files under `src/` were consolidated from the author's tested SpotifyTouch v2.2 Artist and Spotify Appliance v2.0.1/v2.0.2 installations on 2026-11-21.

## Included source

- `src/ubuntu/`: localhost HTTP API; Spicetify/CDP bridge; latest Artist Edition touch UI (top tracks and albums, playlists, Liked Songs, playback, artwork). Final live CSS override: Now Playing `.now-link` is capped at 51% of width with 8 px right padding.
- `src/pi/controller/`: local switch API, on-demand Bluetooth connection, fresh `mpv` consumer.
- `src/pi/kiosk/`: one persistent Electron viewer; MagicMirror/Spotify navigation.
- `src/pi/magicmirror/`: optional MagicMirror launcher and node helper, with final 62–92 px dynamic sizing and monochrome icon.
- `src/pi/session/`: reference minimal labwc configuration and the **legacy migration scripts**, not a fresh-install script.
- `tests/`: fixture-driven API, UI, CDP and Pi switch unit tests.

## Configuration changes from the personal deployment

- Removed real LAN IP, Bluetooth MAC, personal home directory, and fixed device name from published source.
- `SPOTIFY_CONTAINER_NAME`, `SPOTIFY_BRIDGE_PATH`, `SPOTIFY_TOUCH_PORT` configure the Ubuntu API.
- `SPOTIFY_BLUETOOTH_MAC`, `SPOTIFY_CONTROL_PORT`, `SPOTIFY_SWITCH_PORT`, `SPOTIFY_KIOSK_MODE` configure the Pi controller.
- `MAGICMIRROR_URL`, `SPOTIFY_ELECTRON_BIN` configure the viewer and launcher.
- Local SSH keys and audio stream URL belong in privately rendered `systemd` user units (see `examples/systemd`).

## Deliberately not claimed

- This is **not yet a published, clean-install release**. Legacy update installers depended on prior versions and must not be run on a new Pi. A guarded, clean installer and rollback require testing.
- The standalone Pi profile (`SPOTIFY_KIOSK_MODE=standalone`) is preliminary. It needs an independently installed Electron binary and has not been tested without MagicMirror on real Pi hardware.
- The original Spotify Headless container's HTTP audio endpoint and build lifecycle have not been independently reproduced from a fresh container.
- The exact OCI image digest for a reproducible multi-platform pull needs to be selected and verified. The live host reported two RepoDigests for the `latest` image; neither is being assumed authoritative for a new install.
- Bluetooth may be unavailable or unsupported on some devices. Leaving `SPOTIFY_BLUETOOTH_MAC` unset uses the OS default sink rather than attempting pairing.

## Dependency policy

The source files do not include Spotify Headless, proprietary Spotify binaries, persisted user authentication, browser profiles or Spicetify packages. Install them separately from upstream after reviewing their terms. Upstream repository currently does not declare a license. Do not mirror its code into this repository.

A first release should be gated on fresh-install testing (Ubuntu and Pi), rollback, security review and end-to-end playback/artist navigation.