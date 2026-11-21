# SpotifyTouch

Touch-first Spotify controller for small Raspberry Pi displays, with an optional MagicMirror² kiosk integration.

> **Status: source consolidation in progress.** This is a documentation-first public repository. The complete, portable installer is **not yet published or verified**. Do not attempt to install from this repository yet.

## What the working prototype does

The reference deployment uses a Raspberry Pi Zero 2 W (64-bit Debian 13, 7-inch touch display) and an **external x86-64 Ubuntu host** running [Spotify Headless](https://github.com/kk-spartans/spotify-headless) in rootless Podman.

- Touch-friendly Liked Songs, playlists, currently playing tracks, playback controls and artwork.
- Tap the current artist to browse popular tracks and albums; open albums and play tracks.
- Optional MagicMirror² integration with one persistent kiosk viewer that switches between the mirror and Spotify screens.
- Minimal labwc/Wayland display session on the Pi.
- On-demand `mpv` audio consumer and Bluetooth speaker connection.
- SSH tunnel for the control API; separate LAN audio transport.

The working system has been tested on the author's hardware. This repository will progressively publish the **reproducible source and installation process** rather than relying on old machine-specific update archives.

## Architecture

```text
                  Raspberry Pi (ARM64, display)
       ┌─────────────────────────────────────────────────┐
       │ Minimal labwc + persistent Electron kiosk       │
       │   MagicMirror² server-only  ↔  SpotifyTouch UI   │
       │                                                  │
       │ Control API ← local SSH forward :16080           │
       │ Audio      ← mpv ← LAN HTTP MPEG-TS :18080       │
       │                      ↓                           │
       │               PipeWire → Bluetooth               │
       └─────────────────────────────────────────────────┘
                                      ↑
                  x86-64 Ubuntu host  │
       ┌─────────────────────────────────────────────────┐
       │ rootless Podman / Spotify Headless / Spicetify   │
       │ CDP bridge → local SpotifyTouch Python API      │
       │ HTTP audio stream producer                       │
       └─────────────────────────────────────────────────┘
```

**The backend is not running on the Pi.** Upstream Spotify Headless relies on a desktop Spotify client not available as a native ARM64 binary. A "standalone" Pi mode is planned to run the touchscreen *without MagicMirror*, but will still require an external compatible Spotify backend.

## Planned installation profiles

| Profile | Pi display | Ubuntu backend | Status |
| --- | --- | --- | --- |
| MagicMirror integration | Mirror ↔ Spotify touchscreen | Required | Working prototype; portable installer pending |
| Spotify-only kiosk | Spotify touchscreen on boot | Required | Planned; not yet validated |

## Repository and dependencies

- **This repository:** touchscreen UI, API bridge, Pi kiosk/switching code, installer templates and tests.
- **[Spotify Headless](https://github.com/kk-spartans/spotify-headless):** a separately installed upstream dependency. We will pin a tested upstream revision and review new versions through pull requests; we will not silently track `latest` in releases.
- **[MagicMirrorPiO2W](https://github.com/quasialex/MagicMirrorPiO2W):** the separate, optional dashboard integration repository.

Read [architecture](docs/architecture.md), [current integration gaps](docs/integration-gaps.md), and [what configuration is still needed](docs/configuration-inventory.md).

## Security and compatibility

- Never commit Spotify authentication state, browser profiles, credentials, user session files, SSH keys, private calendar URLs, or Bluetooth pairing databases.
- Audio HTTP ports should only be exposed on a trusted network; the control API should remain loopback-bound and accessed through an SSH forward.
- This is an **unofficial** integration, not affiliated with or endorsed by Spotify or MagicMirror². Internal Spotify/Spicetify interfaces are subject to change. Use of Spotify services is subject to Spotify's applicable terms.
- No upstream Spotify client binaries or Spotify Headless source are included.
- Project licensing for original source will be decided before the first code release. Any third-party code and artwork must retain appropriate rights and notices.

## Development roadmap

1. Inventory the exact working Ubuntu and Pi services, without collecting secrets.
2. Consolidate the latest Artist Edition UI/API and Pi kiosk/switcher into clean, configurable source.
3. Replace hardcoded host IPs, usernames and Bluetooth addresses with installer-provided configuration.
4. Test fresh installs, rollbacks, audio lifecycle, artist navigation and both display profiles.
5. Publish a versioned release and then integrate it optionally with MagicMirrorPiO2W.

**Do not run the old version-specific migration scripts as if they were a new-machine installer.**
