#!/usr/bin/env bash
# Offline checks only. Does not use network, Podman, systemd or MagicMirror.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 -m py_compile src/ubuntu/server.py src/pi/controller/switchd.py src/pi/session/patch_launcher.py
python3 -m unittest discover -s tests -q
while IFS= read -r -d '' path; do node --check "$path"; done < <(find src -name '*.js' -print0)
for test in tests/*.js; do node "$test"; done
bash -n src/pi/kiosk/launch-viewer.sh src/pi/session/minimal-session.sh
echo 'Offline checks passed.'