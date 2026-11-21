# Interactive installation (beta / unverified on a fresh device)

> **Read before running:** These are **beta installers** derived from one known-working
> Pi Zero 2 W + Ubuntu deployment. Tests run offline, but a true new-device
> installation and the **Spotify-only profile have not been hardware-tested**.
> Do **not** run them against the author's already-working SpotifyTouch deployment:
> they intentionally refuse to overwrite an existing SpotifyTouch service.
> They do not install or configure an operating system from scratch.

## Prerequisites

- **Ubuntu:** x86-64 Linux, a rootless Podman setup with sufficient memory/disk,
  systemd user session and network access. Spotify Headless is a separately
  installed [upstream project](https://github.com/kk-spartans/spotify-headless).
  Read its applicable terms and security notes. Do not use rootful Podman.
- **Pi:** Raspberry Pi OS Debian 13, labwc/Wayland **already installed and configured**,
  accessible via SSH for recovery; Python 3, systemd user services, `mpv`, SSH,
  `curl`, `PipeWire`/`WirePlumber`; BlueZ and `wpctl` if Bluetooth is requested.
  A MagicMirror companion installation needs an existing MagicMirror + correct
  PM2 launcher registration + its Electron executable. The Spotify-only mode
  needs an independent Electron runtime; the wizard can install it through npm.
- **Network:** Pi can connect to Ubuntu via SSH and TCP port 18080 on a trusted
  LAN. The control API stays bound to Ubuntu loopback and is forwarded over SSH.
  Never expose TCP 16080 directly to the Internet.
- **Spotify login:** a new upstream container requires interactive login in its
  local web interface; the wizard **does not** handle credentials.

## Step 1 — Ubuntu backend

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-ubuntu.sh
```

The wizard asks whether to use an **existing running** Spotify Headless container
or create a new one. The default HTTP mapping for a new container is
`0.0.0.0:18080 → container:8080`, enabling Pi-side audio streaming over the LAN.
It installs the Python API on `127.0.0.1:16080`, copies the project's CDP
bridge into the container's persistent `/data`, and registers the API with
systemd user services. It never copies your Spotify login state into Git.

New container deployment is **experimental**. It uses upstream
`ghcr.io/kk-spartans/spotify-headless:latest` unless you provide an immutable
image ref with `--image`. Replacing `latest` with a vetted release digest is
recommended. Only the audio HTTP endpoint is needed; no extra container
service or external WebRTC ports are required by the Pi client.

**Review the configuration without making changes:**

```bash
bash scripts/install-ubuntu.sh --dry-run --container-mode existing --container spotify-headless
```

## Step 2 — Raspberry Pi frontend

```bash
git clone https://github.com/quasialex/SpotifyTouch.git
cd SpotifyTouch
bash scripts/install-pi.sh
```

Choose one of two modes:

- **1 — Spotify-only:** launch the touchscreen Spotify player without installing
  MagicMirror. Uses a dedicated Electron runtime, optionally installed into a
  separate user directory via npm. This mode is **not yet device-tested**.
- **2 — MagicMirror companion:** keep MagicMirror server-only under an existing,
  healthy PM2 installation and navigate a single persistent Electron viewer
  between MagicMirror and Spotify Touch. An optional launcher is installed.
  If `MMM-KumaSummary` is present, the button is placed next to it; otherwise
  the launcher appears in the top-right corner.

The wizard requests the Ubuntu hostname or IP, SSH login and key path, audio
stream URL (defaults to `http://<ubuntu-host>:18080/spotify.ts`), and optional
paired Bluetooth MAC. It will help create and authorize a dedicated SSH key
with `ssh-copy-id` only after your approval. It requires SSH host-key verification.
**Never upload the private key or authenticated Spotify session.**

Audio starts on entering Spotify; it stops on returning to MagicMirror. PipeWire,
Bluetooth daemon and SSH tunnel remain present but lightweight in the mirror
mode. If no Bluetooth address is configured, the OS default audio sink is used.

**Review the generated plan without making changes:**

```bash
bash scripts/install-pi.sh --dry-run --profile companion \
  --ssh-host ubuntu.example.lan --ssh-user spotify

bash scripts/install-pi.sh --dry-run --profile standalone \
  --ssh-host ubuntu.example.lan --ssh-user spotify
```

The Pi script does **not automatically change the LightDM login session**. The
existing desktop should remain available for the initial switching test. Only
**after** verifying the touch UI and SSH recovery, opt in to a minimal labwc
session:

```bash
bash ~/.local/share/spotify-appliance-v2-kiosk/minimal-session.sh --check
bash ~/.local/share/spotify-appliance-v2-kiosk/minimal-session.sh --enable
# Review the output and SSH recovery instructions BEFORE rebooting.
```

If your Pi does not already have a working labwc/LightDM session, the wizard
will stop and explain the missing prerequisite rather than replacing the OS.

## Rollback and diagnostics

Each installer snapshots any files it writes under
`~/.local/state/spotifytouch/backups/` and saves the last installation manifest.

```bash
# On Ubuntu, from the repository checkout:
bash scripts/rollback-ubuntu.sh

# On the Pi, from its repository checkout:
bash scripts/rollback-pi.sh
```

The rollback preserves user-created SSH keys, Spotify login data, Podman volumes,
and any existing OS/LightDM modifications. A newly created container is *not*
automatically deleted by rollback; inspect and remove it manually if appropriate.
The minimal labwc session has a separate `--restore` command and may require a
reboot. Back up the SD card before changing the graphical boot session.

```bash
# Ubuntu
curl -fsS 'http://127.0.0.1:16080/api?action=health'
systemctl --user status spotify-touch-api.service

# Pi
curl -fsS 'http://127.0.0.1:16181/health'
curl -fsS 'http://127.0.0.1:16080/api?action=health'
systemctl --user status spotify-tunnel.service spotify-appliance-kiosk.service
```

**Known limitations:** the Spotify-only profile's ability to recover when a
Bluetooth speaker is powered on *after* boot needs a device test. The latest
upstream image, container login behavior, screen rotation/mapping and audio
latency remain environment-dependent. No public release tag should imply these
have been validated yet.