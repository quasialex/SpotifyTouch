# SpotifyTouch

Touch-friendly Spotify player for a **Raspberry Pi with a 7-inch display**. Originally built for a **Pi Zero 2 W + SpotPear 7-inch touchscreen** running Debian 13/labwc alongside MagicMirror², but MagicMirror is **optional**.

Play Liked Songs and playlists; tap the now-playing artist for top tracks and albums; navigate with touch, see album artwork, and control playback. Optional Bluetooth audio connects when Spotify opens.

**Two modes:** **1 — Spotify-only** fills the Pi screen (no MagicMirror); **2 — MagicMirror companion** switches between your dashboard and Spotify. Both modes use an **external x86-64 Linux/Ubuntu host** running [Spotify Headless](https://github.com/kk-spartans/spotify-headless); the Spotify desktop backend cannot run natively on a Pi Zero 2 W.

> **Beta:** The original Ubuntu + Pi/MagicMirror setup works. The new interactive installers and Spotify-only mode have **not been tested on a fresh physical installation**. Installers will not overwrite an existing SpotifyTouch deployment.

## Install (Ubuntu first, then Raspberry Pi)

### 1. Ubuntu: Spotify backend

On an **x86-64 Ubuntu** computer, install the prerequisites as your normal user (use `sudo` only for the packages):

```bash
sudo apt update
sudo apt install -y git python3 podman openssh-server
sudo systemctl enable --now ssh
```

Run the interactive installer:

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-ubuntu.sh
```

The wizard detects an existing **Spotify Headless** Podman container or offers to create one. Press Enter for the usual defaults: container `spotify-headless`, audio HTTP port **18080**, private control API port **16080**. It installs the SpotifyTouch API and starts its user service. It **does not ask for your Spotify password**.

If a new container is created, open `http://UBUNTU-IP:18080/` in your browser and complete Spotify Headless's login instructions. On Ubuntu, `hostname -I` displays the local IP address. The audio port must be reachable from your Pi on your trusted LAN.

Already running Spotify Headless with a different external port? Pass it to the installer, for example `bash scripts/install-ubuntu.sh --stream-port 19000`.

**Docker users:** [Spotify Headless's upstream README](https://github.com/kk-spartans/spotify-headless#readme) documents its Docker setup. The **SpotifyTouch Ubuntu installer currently uses Podman**, so use Podman for the automated setup (or adapt the bridge yourself). We do not bundle or modify Spotify Headless.

### 2. Raspberry Pi: touchscreen

Start with a **working Raspberry Pi OS/Debian 13 labwc/Wayland desktop session** and SSH access. Install prerequisites:

```bash
sudo apt update
sudo apt install -y git python3 curl openssh-client mpv labwc pipewire pipewire-pulse wireplumber
```

For **optional Bluetooth audio**, also run `sudo apt install -y bluez`, pair your speaker with `bluetoothctl`, and find its address with `bluetoothctl devices`. For **Spotify-only** mode, also install `nodejs npm` if not present; the wizard can install an isolated Electron runtime. **MagicMirror companion** requires an existing working MagicMirror² installation with PM2 and Electron.

Confirm you can SSH from the Pi to Ubuntu at least once, so its host key is known:

```bash
ssh YOUR_UBUNTU_USER@UBUNTU-IP
# Exit the SSH session with: exit
```

Then run on the Pi:

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-pi.sh
```

The wizard asks for:

1. **Mode:** `1` Spotify-only, or `2` MagicMirror companion.
2. **Ubuntu host/IP** — enter it **once**; the wizard derives the audio URL and SSH connection.
3. **Ubuntu SSH username** — often the same as your Pi username, but check with `whoami` on Ubuntu.
4. **Bluetooth speaker address** (optional; leave blank for your system's default audio).

It can create and authorize a dedicated SSH key using `ssh-copy-id` after asking permission. It then writes the configuration and systemd services for you. **No environment-file editing is required for the normal setup.**

**Different audio port?** Use the same `--stream-port` value on the Pi as on Ubuntu. You can pass known values directly: `bash scripts/install-pi.sh --ssh-host UBUNTU-IP --ssh-user YOUR_UBUNTU_USER`.

### 3. Check and manage

```bash
# On Ubuntu
curl -fsS 'http://127.0.0.1:16080/api?action=health'
systemctl --user status spotify-touch-api.service

# On the Pi
curl -fsS 'http://127.0.0.1:16181/health'
systemctl --user status spotify-appliance-kiosk.service spotify-tunnel.service
```

The Pi wizard creates **`~/.config/spotifytouch/pi.env`**. If you move your Ubuntu server or change speakers later, edit that single file with `vim ~/.config/spotifytouch/pi.env`, then run `systemctl --user restart spotify-tunnel.service spotify-appliance-switch.service spotify-appliance-kiosk.service`. The Ubuntu installer creates `~/.config/spotifytouch/ubuntu.env` automatically.

To try either wizard **without making changes**, use `bash scripts/install-ubuntu.sh --dry-run` on Ubuntu, or `bash scripts/install-pi.sh --dry-run --ssh-host UBUNTU-IP` on the Pi.

To undo a fresh setup, run **`bash scripts/rollback-ubuntu.sh`** on Ubuntu or **`bash scripts/rollback-pi.sh`** on the Pi (from the same checkout). Backups are managed automatically. The Pi installer does not automatically replace your graphical session; to review the optional minimal labwc startup later, run `bash ~/.local/share/spotify-appliance-v2-kiosk/minimal-session.sh --check` first.

## Compatibility and links

- **Pi:** tested reference device: Pi Zero 2 W with SpotPear 7-inch touch panel, Debian 13, labwc, PipeWire; other touchscreens may need a display/touch mapping adjustment.
- **Ubuntu:** x86-64 host with rootless [Podman](https://podman.io/), Spotify Headless, LAN access, and SSH.
- **Optional MagicMirror:** existing [MagicMirror²](https://github.com/MagicMirrorOrg/MagicMirror) or [MagicMirrorPiO2W](https://github.com/quasialex/MagicMirrorPiO2W) installation.
- For the service layout and troubleshooting commands, see [Technical reference](docs/technical.md).

**License:** MIT for SpotifyTouch's original code; see [NOTICE](NOTICE.md) for third-party branding and dependencies. SpotifyTouch is an unofficial project, not affiliated with Spotify.
