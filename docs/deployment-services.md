# Sanitized deployment service inventory

Captured from the author's functioning two-host reference setup on 2026-11-21. This document intentionally includes **no real hostname, IP, Bluetooth hardware address, SSH key material, username or Spotify account data**.

## Ubuntu

| Component | Reference | Purpose |
|---|---|---|
| Spotify Headless | rootless Podman, `ghcr.io/kk-spartans/spotify-headless:latest` | Desktop Spotify + Spicetify/CDP environment |
| `spotify-touch-api.service` | user systemd service | Python API, loopback-only `127.0.0.1:16080` |
| Spotify audio stream | Podman port publication `18080 -> container 8080/tcp` | MPEG-TS feed consumed by the Pi |

`latest` describes the **existing live host**, not a recommended deployment dependency. An immutable image digest and the container startup/persistence configuration still need to be captured. The audio producer is **inside or behind** the container's published HTTP endpoint; its creation has not been independently documented. Do not invent a second host-side streaming daemon.

**Security note:** the live reference port `18080` listens on all Ubuntu interfaces. Public installs should restrict it to a trusted LAN via binding/firewalling. The control API must stay loopback-only.

## Raspberry Pi

| User service | Lifecycle | Dependency |
|---|---|---|
| `spotify-appliance-switch.service` | persistent | local switch API `127.0.0.1:16181`; on-demand audio and Bluetooth orchestration |
| `spotify-appliance-kiosk.service` | persistent | one Electron viewer under labwc |
| `spotify-appliance-audio.service` | **not enabled** | `mpv` consumer; started on Spotify entry, stopped on Mirror exit |
| `spotify-tunnel.service` | persistent | SSH forward of Pi `127.0.0.1:16080` to Ubuntu loopback API |

The current reference speaker is paired. Its Bluetooth MAC address is removed from public templates and belongs only in local configuration. The working reference `switchd.py` needs a portability refactor to load this value from config rather than a Python constant.

MagicMirror runs server-only under PM2, with executable launcher `~/MagicMirror/installers/mm.sh`, interpreter `bash`, and working directory `~/MagicMirror`. The Pi's MagicMirror HTTP server binds to `[::1]:8080`. Preserving the working PM2 launcher and saving PM2 state after startup changes is critical; prior stale PM2 definitions caused a crash loop.

## Configuration templates

- [Ubuntu API service](../examples/systemd/ubuntu/spotify-touch-api.service)
- [Pi switch controller service](../examples/systemd/pi/spotify-appliance-switch.service)
- [Pi kiosk viewer service](../examples/systemd/pi/spotify-appliance-kiosk.service)
- [Pi on-demand audio service](../examples/systemd/pi/spotify-appliance-audio.service.in)
- [Pi secure SSH tunnel](../examples/systemd/pi/spotify-tunnel.service.in)
- [Non-secret configuration example](../config/example.env)

The `.in` templates contain deliberate replacement markers. **Do not install them without rendering those markers**, and do not enable the on-demand audio service on boot.

## Follow-up inventory still required

1. Upstream image digest and Podman startup/update mechanism; do not publish `podman inspect` wholesale.
2. The installed audio endpoint/protocol and `/spotify.ts` creation process inside the existing upstream container.
3. Complete SSH tunnel invocation (the pasted service was truncated) and the safe key-provisioning process; never publish a private key.
4. Live final launcher and Now Playing CSS refinements.
5. Standalone Spotify-only kiosk bootstrap, independent of MagicMirror's Electron install.

**Status:** templates only. A release must include a guarded installer, verification, explicit rollback and fresh-device testing before these examples are offered as a one-command setup.
