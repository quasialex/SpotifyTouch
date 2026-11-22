#!/usr/bin/env bash
# Optional dedicated labwc session for Raspberry Pi OS Trixie + Elecrow touch.
# It does not uninstall a desktop or change SSH, Wi-Fi, PipeWire or Bluetooth.
# Must be run AFTER the Spotify Touch installer and a successful touchscreen test.
set -Eeuo pipefail
MODE="${1:---check}"
HERE="$(cd "$(dirname "$0")" && pwd)"
STATE="$HOME/.local/state/spotify-touch"
CONF="$HOME/.config/spotify-touch"
LABWC="$CONF/labwc"
MARKER="$STATE/minimal-backup"
LIGHTDM=/etc/lightdm/lightdm.conf
SESSION=/usr/share/wayland-sessions/spotify-touch.desktop
SESSION_SCRIPT=/usr/local/bin/spotify-touch-session
fail(){ echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -ne 0 ]] || fail 'Run as regular user, not sudo.'
mkdir -p "$STATE"
if [[ "$MODE" == --check ]];then
  echo 'No changes made.'
  echo 'Configured login session:'
  grep -E '^[[:space:]]*autologin-session=' "$LIGHTDM" 2>/dev/null || true
  echo 'Available Wayland sessions:'
  ls /usr/share/wayland-sessions/*labwc*.desktop 2>/dev/null || true
  echo 'Existing user display configuration:'
  ls -l "$HOME/.config/labwc" "$HOME/.config/kanshi" 2>/dev/null || true
  echo 'Desktop processes currently running:'
  ps -eo comm= | grep -E '^(labwc|wf-panel-pi|pcmanfm-pi|kanshi|swayidle|electron)$' || true
  echo 'Spotify Touch application readiness:'
  curl -fsS -m 3 http://127.0.0.1:16181/health || true
  echo
  echo 'Enable only after the Spotify Touch touchscreen app works and SSH/SD backup are available.'
  exit 0
fi
if [[ "$MODE" == --enable ]]; then
  [[ ! -f "$MARKER" ]] || fail 'Already enabled. Use --restore first.'
  [[ -f "$CONF/enabled" ]] || fail 'Install and test Spotify Touch first.'
  [[ -x /usr/bin/labwc ]] || fail 'labwc binary missing.'
  [[ -f "$LIGHTDM" ]] || fail 'LightDM config not found.'
  python3 - "$LIGHTDM" <<'PY' || fail 'Cannot find a single supported autologin-session setting.'
from pathlib import Path
import re,sys
v=Path(sys.argv[1]).read_text()
a=re.findall(r'^\s*autologin-session\s*=\s*([^#\s]+)',v,re.M)
assert len(a)==1 and a[0] in ('rpd-labwc','labwc'), f'Unexpected session setting: {a}'
PY
  BK="$HOME/spotify-touch-backups/$(date +%Y%m%d-%H%M%S)-minimal-$$"
  mkdir -p "$BK" "$LABWC"
  sudo cp -a "$LIGHTDM" "$BK/lightdm.conf"
  [[ ! -f "$SESSION" ]] || sudo cp -a "$SESSION" "$BK/session.desktop"
  [[ ! -f "$SESSION_SCRIPT" ]] || sudo cp -a "$SESSION_SCRIPT" "$BK/session-script"
  [[ ! -f "$LABWC/rc.xml" ]] || cp -a "$LABWC/rc.xml" "$BK/rc.xml"
  [[ ! -f "$LABWC/environment" ]] || cp -a "$LABWC/environment" "$BK/environment"
  [[ ! -f "$LABWC/autostart" ]] || cp -a "$LABWC/autostart" "$BK/autostart"
  # Preserve existing touch and output settings where possible. A custom
  # config directory avoids the Pi desktop system autostart (panel/file manager).
  if [[ -f "$HOME/.config/labwc/rc.xml" ]];then
    cp -a "$HOME/.config/labwc/rc.xml" "$LABWC/rc.xml"
  elif [[ -f /etc/xdg/labwc/rc.xml ]]; then
    cp -a /etc/xdg/labwc/rc.xml "$LABWC/rc.xml"
  else
    cat > "$LABWC/rc.xml" <<'XML'
<?xml version="1.0"?>
<labwc_config><core><gap>0</gap></core></labwc_config>
XML
  fi
  if [[ -f "$HOME/.config/labwc/environment" ]];then
    cp -a "$HOME/.config/labwc/environment" "$LABWC/environment"
  elif [[ -f /etc/xdg/labwc/environment ]];then
    cp -a /etc/xdg/labwc/environment "$LABWC/environment"
  fi
  cat > "$LABWC/autostart" <<'AUTO'
#!/bin/sh
# Dedicated, minimal labwc session. No desktop panel/file-manager/XDG autostart.
# Preserve monitor rotation if the user has existing kanshi configuration.
if command -v kanshi >/dev/null 2>&1; then kanshi >/dev/null 2>&1 & fi
# Let systemd user services discover the active Wayland display.
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP >/dev/null 2>&1 || true
# Viewer service is enabled at boot; restart it to attach to this compositor.
systemctl --user --no-block restart spotify-touch-kiosk.service >/dev/null 2>&1 || true
AUTO
  chmod 0755 "$LABWC/autostart"
  printf '#!/bin/sh\nexport WLR_DRM_FORCE_LIBLIFTOFF=1\nexec /usr/bin/labwc -C "$HOME/.config/spotify-touch/labwc"\n' > "$BK/new-session-script"
  cat > "$BK/new-session.desktop" <<'DESKTOP'
[Desktop Entry]
Name=Spotify Touch Kiosk
Comment=Minimal labwc touchscreen for MagicMirror and Spotify Touch
Exec=/usr/local/bin/spotify-touch-session
TryExec=/usr/bin/labwc
Type=Application
DesktopNames=labwc
DESKTOP
  # Use a full copy of lightdm.conf rather than a conf.d override: on Raspberry
  # Pi OS the main file can take precedence over drop-ins.
  python3 - "$LIGHTDM" "$BK/new-lightdm.conf" <<'PY'
from pathlib import Path
import re,sys
text=Path(sys.argv[1]).read_text()
new,count=re.subn(r'(?m)^(\s*autologin-session\s*=\s*)(rpd-labwc|labwc)(\s*)$',
                  r'\g<1>spotify-touch\g<3>',text)
assert count==1, 'Could not patch exactly one LightDM session'
Path(sys.argv[2]).write_text(new)
PY
  # A failed privileged operation rolls LightDM back before returning.
  succeeded=0
  rollback_on_error(){
    rc=$?;trap - EXIT
    if (( rc != 0 && succeeded == 0 ));then
      sudo cp -a "$BK/lightdm.conf" "$LIGHTDM" || true
      sudo rm -f "$SESSION" "$SESSION_SCRIPT" || true
      [[ ! -f "$BK/session.desktop" ]] || sudo cp -a "$BK/session.desktop" "$SESSION"
      [[ ! -f "$BK/session-script" ]] || sudo cp -a "$BK/session-script" "$SESSION_SCRIPT"
      echo "Minimal session failed; original LightDM restored. Backup: $BK" >&2
    fi
    exit "$rc"
  }
  trap rollback_on_error EXIT
  sudo install -m 0755 "$BK/new-session-script" "$SESSION_SCRIPT"
  sudo install -m 0644 "$BK/new-session.desktop" "$SESSION"
  sudo install -m 0644 "$BK/new-lightdm.conf" "$LIGHTDM"
  printf '%s\n' "$BK" > "$MARKER"
  succeeded=1
  trap - EXIT
  echo "Minimal kiosk session configured. BACKUP: $BK"
  echo 'No reboot was performed. After verifying SSH access and SD-card backup:'
  echo '  sudo reboot'
  echo 'If display/touch rotation fails, recover over SSH:'
  echo "  bash $HERE/minimal-session.sh --restore && sudo reboot"
  exit 0
fi
if [[ "$MODE" == --restore ]]; then
  [[ -f "$MARKER" ]] || fail 'No minimal session backup recorded.'
  BK="$(cat "$MARKER")"
  [[ -f "$BK/lightdm.conf" ]] || fail 'Missing backup: original LightDM configuration.'
  sudo cp -a "$BK/lightdm.conf" "$LIGHTDM"
  sudo rm -f "$SESSION" "$SESSION_SCRIPT"
  [[ ! -f "$BK/session.desktop" ]] || sudo cp -a "$BK/session.desktop" "$SESSION"
  [[ ! -f "$BK/session-script" ]] || sudo cp -a "$BK/session-script" "$SESSION_SCRIPT"
  rm -f "$LABWC/autostart" "$LABWC/rc.xml" "$LABWC/environment"
  for f in autostart rc.xml environment; do
    [[ ! -f "$BK/$f" ]] || cp -a "$BK/$f" "$LABWC/$f"
  done
  rm -f "$MARKER"
  echo 'Original LightDM session and prior kiosk config restored. Reboot manually.'
  exit 0
fi
fail 'Usage: minimal-session.sh --check | --enable | --restore'