#!/usr/bin/env bash
set -Eeuo pipefail
USER_ID="$(id -u)"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$USER_ID}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=labwc
FOUND_WAYLAND=0
for _ in $(seq 1 180); do
  for socket in "$XDG_RUNTIME_DIR"/wayland-*; do
    if [[ -S "$socket" ]]; then
      export WAYLAND_DISPLAY="$(basename "$socket")"
      FOUND_WAYLAND=1
      break 2
    fi
  done
  sleep 1
done
(( FOUND_WAYLAND )) || { echo 'Wayland display not ready' >&2; exit 1; }
FOUND_SERVERS=0
SWITCH_PORT="${SPOTIFY_SWITCH_PORT:-16181}"
for _ in $(seq 1 100); do
  if curl --noproxy '*' -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:$SWITCH_PORT/health" >/dev/null 2>&1; then
    if [[ "${SPOTIFY_KIOSK_MODE:-mirror}" == "standalone" ]] || \
       curl --noproxy '*' -g -fsS --connect-timeout 1 --max-time 2 "${MAGICMIRROR_URL:-http://[::1]:8080/}" >/dev/null 2>&1; then
      FOUND_SERVERS=1
      break
    fi
  fi
  sleep 1
done
(( FOUND_SERVERS )) || { echo 'Kiosk prerequisites failed: local switch controller or MagicMirror unavailable' >&2; exit 1; }
ELECTRON_BIN="${SPOTIFY_ELECTRON_BIN:-$HOME/MagicMirror/node_modules/.bin/electron}"
[[ -x "$ELECTRON_BIN" ]] || { echo 'Electron binary missing; configure SPOTIFY_ELECTRON_BIN' >&2; exit 1; }
exec "$ELECTRON_BIN" "$HOME/.local/share/spotify-touch/electron-kiosk.js" --ozone-platform=wayland