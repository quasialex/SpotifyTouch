# Gap analysis: SpotifyTouch vs MagicMirrorPiO2W

Target dashboard repository: [quasialex/MagicMirrorPiO2W](https://github.com/quasialex/MagicMirrorPiO2W), default branch `master`.

## Existing dashboard repository

Its current `pio2w-dashboard/` profile contains a MagicMirror config and modules for calendars, RSS, touch routing, pages and Kuma status. It does **not** contain the current `MMM-SpotifyTouch` module, standalone switch controller, kiosk viewer, Bluetooth/audio service lifecycle or minimal labwc session.

The root `mm.sh` and `pm2_MagicMirror.json` are installation-era examples rather than a verified representation of the current working Pi configuration. The live Pi successfully runs PM2 with `script=~/MagicMirror/installers/mm.sh`, interpreter `bash`, cwd `~/MagicMirror`. The new portable integration must preserve that contract and avoid resurrecting stale PM2 definitions.

## Existing installer hazards to fix separately

In `pio2w-dashboard/install-dashboard.sh`:

- The script claims to preserve an existing `config.js`, but its else branch still downloads and overwrites it.
- A module synchronization uses `rsync -a --delete` against `MagicMirror/modules`, which can delete unrelated modules not included in the dashboard profile.

Neither issue should be carried into the SpotifyTouch integration. Do not change `MagicMirrorPiO2W` until the SpotifyTouch installer is ready and tested.

## Proposed integration

- Keep SpotifyTouch fully independent. Its Raspberry Pi installation will have **Spotify-only** and **MagicMirror** profiles.
- The MagicMirror profile installs only the `MMM-SpotifyTouch` module and the kiosk/switch/audio services, with isolated backups and reversible activation.
- `MagicMirrorPiO2W` provides an **optional** wrapper/install option that fetches a pinned SpotifyTouch release/tag, not a copied or forked codebase.
- All machine-specific values (upstream host, audio-stream URL, SSH user/host, Bluetooth MAC, MagicMirror directory) must come from local config, not source defaults.

## Publication checklist

- [ ] No secrets or private account state in Git history
- [ ] Upstream image pinned by digest or tested release reference
- [ ] Complete audio producer and SSH tunnel setup documented
- [ ] Fresh-install and rollback tests
- [ ] Spotify-only profile verified independently of MagicMirror
- [ ] No destructive overwrites of user MagicMirror modules/config
- [ ] User-visible docs reflect actual capabilities and dependencies
