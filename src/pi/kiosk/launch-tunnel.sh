#!/usr/bin/env bash
# No networking credentials or device IPs are baked into systemd unit files.
set -Eeuo pipefail
: "${SPOTIFY_UBUNTU_HOST:?Set SPOTIFY_UBUNTU_HOST in pi.env}"
: "${SPOTIFY_UBUNTU_USER:?Set SPOTIFY_UBUNTU_USER in pi.env}"
: "${SPOTIFY_SSH_IDENTITY_FILE:?Set SPOTIFY_SSH_IDENTITY_FILE in pi.env}"
exec /usr/bin/ssh -N -T -o BatchMode=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=yes -i "$SPOTIFY_SSH_IDENTITY_FILE" \
  -L 127.0.0.1:16080:127.0.0.1:16080 \
  "${SPOTIFY_UBUNTU_USER}@${SPOTIFY_UBUNTU_HOST}"