# Installation and rollback

> **Beta:** no clean-install hardware validation yet. The installers do not overwrite an existing SpotifyTouch installation and do not reinstall the operating system. Use a normal (non-root) user with an available systemd user session.

## 1. Ubuntu backend

On an **x86-64 Ubuntu** machine, install rootless Podman, then:

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-ubuntu.sh
```

The wizard chooses **existing Spotify Headless container** by default when it detects one, otherwise **create a new container**. The default name is `spotify-headless`; newly created containers use the separate upstream image `ghcr.io/kk-spartans/spotify-headless:latest` and preserve `/data` in a Podman volume. The upstream `latest` tag is mutable; an immutable image can be provided with `--image`. No Spotify source code, browser profile, cookies or credentials are added to this repository.

The wizard installs the Python API as `spotify-touch-api.service` on Ubuntu **loopback** `127.0.0.1:16080`. The HTTP stream uses the container's `/spotify.ts` endpoint (Ubuntu TCP `18080` by default). After creating a new container, complete Spotify login through the upstream container's web page at `http://<ubuntu-host>:18080/`. Restrict this port to a trusted LAN using a firewall; never forward it to the Internet.

For review only (no writes):

```bash
bash scripts/install-ubuntu.sh --dry-run
```

## 2. Raspberry Pi touchscreen

On a Pi running **Debian 13 / Raspberry Pi OS with a working labwc/Wayland session**, install `mpv`, `curl`, SSH client, Python 3, PipeWire/WirePlumber and systemd user services. Install `bluetoothctl`/`wpctl` if using Bluetooth. Keep SSH recovery available.

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-pi.sh
```

Choose one of these modes:

- **1 — Spotify-only:** dedicated fullscreen kiosk; independent Electron runtime (the wizard can install one with npm). **Not tested on physical standalone hardware.**
- **2 — MagicMirror companion:** MagicMirror must already be installed and managed with a working PM2 launcher. The wizard installs `MMM-SpotifyTouch`, a single Electron viewer and on-demand audio; MagicMirror stays server-only while Spotify is open.

The wizard asks only for the **Ubuntu host/IP**, **Ubuntu SSH user** (defaults to your current username) and **optional paired Bluetooth MAC**. The default stream URL is automatically `http://<ubuntu-host>:18080/spotify.ts`; no second Ubuntu address is needed. If the audio endpoint differs, use `--stream-port` or `--audio-url`.

It generates one private file, `~/.config/spotifytouch/pi.env`, used by the local controller, kiosk, audio and SSH tunnel. The SSH identity can be created and authorized with your approval (`ssh-copy-id`); the script uses strict SSH host-key checking. Never commit private keys or login state. The on-demand `mpv` audio service is **not** enabled at startup.

For review only (no writes):

```bash
bash scripts/install-pi.sh --dry-run --ssh-host ubuntu.example.lan
```

The wizard **does not change your graphical login session**. After verifying the viewer, audio and SSH recovery, the optional minimal labwc session can be reviewed and enabled with:

```bash
bash ~/.local/share/spotify-appliance-v2-kiosk/minimal-session.sh --check
bash ~/.local/share/spotify-appliance-v2-kiosk/minimal-session.sh --enable
```

This optional step adjusts LightDM and may require a reboot. It has its own `--restore` command. Do not enable it without SSH recovery access.

## Diagnostics and rollback

```bash
# Ubuntu
curl -fsS 'http://127.0.0.1:16080/api?action=health'
systemctl --user status spotify-touch-api.service

# Pi
curl -fsS 'http://127.0.0.1:16181/health'
curl -fsS 'http://127.0.0.1:16080/api?action=health'
systemctl --user status spotify-tunnel.service spotify-appliance-kiosk.service
```

To undo a new setup, from the same repository checkout:

```bash
# On Ubuntu
bash scripts/rollback-ubuntu.sh

# On Pi
bash scripts/rollback-pi.sh
```

Backups are recorded under `~/.local/state/spotifytouch/backups/`. Rollback restores installer-managed files and user services. It intentionally leaves Spotify user data, newly created Podman volumes/containers and generated SSH keys available for review rather than deleting them. If you enabled the optional minimal session, run `minimal-session.sh --restore` separately.

**Limitations:** Pi standalone mode, new-container startup on fresh Ubuntu, and the complete rollback have not been validated on a second physical deployment. The runtime relies on Spotify/Spicetify private interfaces, which can change independently. If you use upstream `latest`, check compatibility after a new image pull; no automatic upgrades are performed by this project.