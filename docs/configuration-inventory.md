# Live configuration still needed

The release archives preserve most of the touchscreen UI and kiosk logic, but **not** the complete live installation. The public repository should use sanitized examples, never raw production configuration.

## Ubuntu inventory to capture privately

- `systemctl --user cat spotify-touch-api.service`
- `podman ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'`
- `podman port spotify-headless`
- Container **immutable image digest** or `podman image inspect` *limited to digest fields*, not a full container inspect
- How the MPEG-TS stream producer on port `18080` is launched and configured
- Current API/bridge source, already available in the last Artist Edition archive
- Dependencies and directory layout required for a fresh installation

## Pi inventory to capture privately

- `systemctl --user cat spotify-appliance-{switch,kiosk,audio}.service spotify-tunnel.service`
- The active `MMM-SpotifyTouch` module's JS, CSS and node helper
- Current final manual CSS changes to launcher and Now Playing area
- The local `labwc` session settings (remove screen identity, hardware addresses and user-specific paths)
- MagicMirror launcher and its PM2 script/cwd/interpreter
- Any local Bluetooth setup/connection script or timer units and whether the timer is disabled

## Redact before sharing

**Never include:** authentication tokens, Spotify cookies, session directories, private playlist URLs, calendar ICS links, SSH private keys, Bluetooth pairing secrets, full `podman inspect` outputs, environment files or private certificates.

**Replace before committing:** LAN addresses, usernames, home paths, Bluetooth MAC addresses, specific music account metadata and private URLs.

The repository's future `config/example.env` and installers will define the supported configuration variables once the complete dependency chain is audited.
