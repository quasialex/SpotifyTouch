# SpotifyTouch

A lightweight, touch-first Spotify player for a Raspberry Pi, with an optional **MagicMirror² companion** mode. Designed for a Pi Zero 2 W and a small touchscreen, with an **external x86-64 Ubuntu machine** providing the Spotify backend.

Features: Liked Songs, playlists, artist top tracks and albums, artwork, playback controls, a persistent fullscreen kiosk, and optional on-demand Bluetooth audio.

## Install: Ubuntu first, then Pi

On your **Ubuntu x86-64 host**, with rootless [Podman](https://podman.io/) installed:

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-ubuntu.sh
```

The wizard detects an existing Spotify Headless container or offers to create one. It installs the localhost-only SpotifyTouch API and the Spicetify bridge. A new container will require you to sign in through the upstream Spotify Headless login page. **No Spotify credentials are requested by this installer.**

On your **Raspberry Pi (Debian 13 / labwc)**:

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-pi.sh
```

Choose **1 — Spotify-only kiosk** or **2 — MagicMirror companion**. The wizard asks for the **Ubuntu host/IP once**, Ubuntu SSH username, and optionally a paired Bluetooth speaker address. The audio URL is derived from the Ubuntu host automatically. It creates `~/.config/spotifytouch/pi.env` as the **single source of truth** for Ubuntu connectivity, local audio and the SSH tunnel; you do not edit separate service definitions. In companion mode, MagicMirror must already be installed.

To review the installer without changes: `bash scripts/install-ubuntu.sh --dry-run` or `bash scripts/install-pi.sh --dry-run --ssh-host ubuntu.example.lan`.

**Read [installation requirements and rollback](docs/installation.md) before using a beta installer.** Existing SpotifyTouch installs are detected and left untouched; these are *fresh-setup* scripts, not migration scripts. Minimal labwc/LightDM takeover is an optional later step, not automatic.

## Dependencies and compatibility

- **[kk-spartans/spotify-headless](https://github.com/kk-spartans/spotify-headless)**: separate upstream backend. The installer pulls the published `ghcr.io/kk-spartans/spotify-headless` container image or attaches to one already running. We do not copy, vendor or modify Spotify Headless itself. Its upstream changes are **not automatically deployed** to existing installations.
- **Raspberry Pi**: ARM64 Pi Zero 2 W, existing working labwc/Wayland session, `mpv`, SSH, PipeWire, systemd user services, and an Electron runtime (bundled with MagicMirror or separately installed by the standalone wizard). Bluetooth is optional.
- **Network**: trusted LAN access from the Pi to Ubuntu's HTTP stream on port `18080`, plus SSH access. The SpotifyTouch API listens on Ubuntu `127.0.0.1:16080` and is forwarded via SSH; it is **not** published on the LAN.
- **[quasialex/MagicMirrorPiO2W](https://github.com/quasialex/MagicMirrorPiO2W)**: separate MagicMirror installation project. SpotifyTouch companion mode can integrate with an existing MagicMirror without copying its sources into this repository.

## Beta status

Based on one working Ubuntu + Pi Zero 2 W deployment. **Offline tests and GitHub Actions pass, but the fresh-device installers and Spotify-only mode have not been tested on physical hardware.** Some devices may need display mapping, speaker or SSH adjustments. You should have SSH recovery access and a Pi backup before altering its graphical session. The installer's backup/rollback code has offline coverage but has not been exercised through a complete clean installation.

The software is unofficial, not endorsed by Spotify or MagicMirror². Spotify service access remains subject to Spotify's terms. **MIT** applies to the original SpotifyTouch code; third-party branding and software are not relicensed (see [NOTICE.md](NOTICE.md)).