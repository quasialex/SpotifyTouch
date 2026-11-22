# Technical reference

SpotifyTouch uses two machines: **Ubuntu** hosts the separate Spotify Headless Podman container and a loopback-only Python/Spicetify bridge; **Raspberry Pi** shows the touchscreen kiosk, connects over an SSH-forwarded control API, and plays the LAN audio stream with `mpv` through PipeWire (optionally Bluetooth). The Pi does **not** run the Spotify desktop application.

| Component | What it does |
| --- | --- |
| Ubuntu `spotify-touch-api.service` | Local control API on `127.0.0.1:16080` |
| Ubuntu Spotify Headless container | Spotify/Spicetify backend and `http://UBUNTU-IP:18080/spotify.ts` audio |
| Pi `spotify-touch-tunnel.service` | SSH forward from local Pi port 16080 to the Ubuntu API |
| Pi `spotify-touch-switch.service` | Switches views and connects/disconnects audio on demand |
| Pi `spotify-touch-kiosk.service` | Persistent fullscreen Electron viewer under labwc |
| Pi `spotify-touch-audio.service` | On-demand `mpv` stream; **not enabled at boot** |

## Managing services

```bash
# Ubuntu
systemctl --user restart spotify-touch-api.service
journalctl --user -u spotify-touch-api.service -n 50 --no-pager
podman ps --filter name=spotify-headless

# Raspberry Pi
systemctl --user status spotify-touch-tunnel.service spotify-touch-switch.service spotify-touch-kiosk.service
journalctl --user -u spotify-touch-switch.service -n 50 --no-pager
curl -fsS http://127.0.0.1:16181/health
```

## Settings

- Pi wizard-generated settings: `~/.config/spotify-touch/pi.env`. One Ubuntu hostname is shared by the tunnel and audio launcher; Bluetooth MAC is optional. To change settings, edit this file and restart the Pi services listed in the README.
- Ubuntu wizard-generated settings: `~/.config/spotify-touch/ubuntu.env`. The API binds only to Ubuntu loopback; the audio stream needs LAN access from the Pi.
- Existing SpotifyTouch installs are intentionally not overwritten by the new-install beta wizard. Use the supplied rollback scripts for files/services created by the wizard.
- MagicMirror companion uses a working MagicMirror server-only instance (normally `[::1]:8080`) and its existing PM2 launcher. Standalone mode uses an isolated Electron runtime and does not require MagicMirror.

**Note:** The Spotify Headless container and Spotify/Spicetify internals may change upstream. The installer does not automatically deploy upstream updates. Fresh-install and standalone-Pi hardware validation remain outstanding.
