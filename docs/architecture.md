# Reference architecture (as observed 2026-11-21)

This describes the working reference system, **not** a generally installable configuration.

## Ubuntu — x86-64 backend

- Rootless Podman container `spotify-headless`, currently sourced from `ghcr.io/kk-spartans/spotify-headless:latest` (the immutable image digest has **not yet been captured**).
- User service `spotify-touch-api.service` runs the Python control API on `127.0.0.1:16080`.
- A Spicetify/CDP helper executes authorized UI requests inside the already-authenticated desktop player context. Its artist overview request was verified live.
- A container-published HTTP MPEG-TS audio feed is listening on Ubuntu port `18080`; its exact producer configuration still needs to be inventoried.
- This is a separately managed upstream dependency: no upstream image or desktop binary belongs in this repository.

## Raspberry Pi — ARM64 touch client

Reference hardware: Pi Zero 2 W, Debian 13 (Trixie), 7-inch touchscreen.

- Custom minimal `labwc` compositor session; no normal desktop panel or file manager.
- MagicMirror² `v2.36.0` runs **server-only** under PM2, through `~/MagicMirror/installers/mm.sh`, listening on **IPv6 loopback** `[::1]:8080`.
- A persistent Electron kiosk viewer displays either the mirror or the Spotify Touch page, instead of restarting a full Electron application at every switch.
- `spotify-appliance-switch.service`: local switch API on `127.0.0.1:16181`.
- `spotify-appliance-kiosk.service`: persistent Electron viewer.
- `spotify-appliance-audio.service`: Pi-side `mpv` audio consumer; starts on Spotify entry and stops on exit.
- `spotify-tunnel.service`: SSH port forward for the control API.
- BlueZ, PipeWire and WirePlumber support an on-demand Bluetooth speaker. The user-supplied MAC address belongs in **local config only**.

## Control flow

1. The user taps the Spotify launcher, or the Pi starts directly in Spotify-only mode (planned).
2. The Pi controller navigates the one viewer to the Spotify Touch UI.
3. On Spotify entry, Bluetooth output is connected/selected and a fresh audio consumer is started.
4. UI actions traverse the loopback SSH control tunnel to the Python API and CDP bridge.
5. A separate HTTP MPEG-TS stream carries audio from Ubuntu to the Pi; `mpv` sends it through PipeWire.
6. On return to MagicMirror, the audio consumer stops and Bluetooth may disconnect; the MagicMirror server and lightweight control tunnel stay running.

## Non-goals

- Running upstream x86-64 Spotify desktop binaries directly on the ARM64 Pi Zero 2 W.
- Exposing the control API to the public Internet.
- Automatically updating `latest` Spotify Headless on deployed installations.
- Restarting MagicMirror, the OS or Bluetooth daemon on each screen change.

## Verified behavior vs assumptions

**Observed:** artist overview with top tracks and albums, successful playlist/artist/album navigation, and reduced audio lag after audio consumer restart on the author's deployment.

**Not yet verified on fresh installations:** container image digest, creation of the audio stream producer, clean SSH tunnel bootstrap, Bluetooth compatibility across speakers, fully standalone touch-only mode, and exact service restart dependencies.
