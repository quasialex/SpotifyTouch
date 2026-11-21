#!/usr/bin/env bash
# Audio URL is derived at service launch from the one Pi configuration file.
set -Eeuo pipefail
: "${SPOTIFY_UBUNTU_HOST:?Set SPOTIFY_UBUNTU_HOST in pi.env}"
url="${SPOTIFY_AUDIO_URL_OVERRIDE:-http://${SPOTIFY_UBUNTU_HOST}:${SPOTIFY_AUDIO_PORT:-18080}/spotify.ts}"
exec /usr/bin/mpv --no-video --ao=pulse --force-window=no --no-terminal \
  --profile=low-latency --cache=no --demuxer-readahead-secs=0 \
  --audio-buffer=0.12 "$url"