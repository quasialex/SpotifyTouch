#!/usr/bin/env python3
"""Spotify Touch beta, two-host setup wizard.  No changes without final confirmation.

Supports rootless Podman on an x86-64 Ubuntu host and a Raspberry Pi with a
working Wayland/labwc session.  A fresh Pi OS installation is out of scope.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
STATE = HOME / '.local/state/spotify-touch'
CONFIG = HOME / '.config/spotify-touch'
USER_UNITS = HOME / '.config/systemd/user'
APP_PI = HOME / '.local/share/spotify-touch'
APP_UBUNTU = HOME / '.local/share/spotify-touch'
CONTROL_PORT = 16080
SWITCH_PORT = 16181


def fail(message):
    raise RuntimeError(message)


def run(args, *, cwd=None, capture=False, check=True):
    result = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if check and result.returncode:
        fail(f"Command failed ({result.returncode}): {args[0]} " +
             ((result.stderr or result.stdout or '')[-500:] if capture else ''))
    return result


def which(binary):
    if shutil.which(binary) is None:
        fail(f"Missing prerequisite: {binary}. Install it separately and retry.")


def yesno(message, default=False, *, noninteractive=False):
    if noninteractive:
        return default
    answer = input(f"{message} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not answer else answer in ('y', 'yes')


def ask(message, default=None, *, noninteractive=False):
    if noninteractive:
        if default is None:
            fail(f"Unattended mode requires: {message}")
        return default
    result = input(f"{message}" + (f" [{default}]" if default else '') + ': ').strip()
    return result or default or ''


def validate_host(host):
    if not host or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.\-]{0,252}', host):
        fail('Host must be an IPv4 address or DNS name without scheme, port or whitespace')
    return host


def validate_user(user):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9-]{0,63}', user or ''):
        fail('Invalid SSH user name')
    return user


def validate_mac(mac):
    if mac and not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', mac):
        fail('Bluetooth address must be empty or six colon-separated hex octets')
    return mac.upper()


def validate_stream(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'http' or not parsed.hostname or parsed.port is None or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            not parsed.path.endswith('.ts') or re.search(r'[\s%$;"\\]', url)):
        fail('Audio stream URL must be plain HTTP host:port/*.ts on a trusted LAN')
    if not (1 <= parsed.port <= 65535):
        fail('Invalid stream port')
    return url


def validate_path(path):
    p = Path(path).expanduser().resolve()
    if re.search(r'[\s%;"\\]', str(p)):
        fail('Path must not contain spaces or shell/systemd metacharacters')
    return p


def systemctl_state(name):
    return {'active': run(['systemctl', '--user', 'is-active', '--quiet', name], check=False).returncode == 0,
            'enabled': run(['systemctl', '--user', 'is-enabled', '--quiet', name], check=False).returncode == 0}


def unit_exec(name):
    return f'{name}.service'


class Transaction:
    """Record backups before every write; supports manual and failed-install rollback."""
    def __init__(self, role, unit_names):
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        self.role = role
        self.folder = STATE / 'backups' / f'{stamp}-{role}-{os.getpid()}'
        self.entries = []
        self.units = {u: systemctl_state(u) for u in unit_names}
        self.container_created = None
        self.container_bridge = None
        self.units_changed = False

    def save(self, dst, payload, mode=0o644):
        dst = Path(dst)
        if not dst.is_absolute() or dst == Path('/'):
            fail('Destination path must be absolute')
        if dst.exists() and not dst.is_file():
            fail(f'Not a regular file: {dst}')
        record = {'path': str(dst), 'exists': dst.exists(), 'mode': None, 'backup': None}
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        if dst.exists():
            key = hashlib.sha256(str(dst).encode()).hexdigest()[:24]
            record['backup'] = key
            record['mode'] = dst.stat().st_mode & 0o777
            shutil.copy2(dst, self.folder / key)
        self.entries.append(record)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + '.spotifytouch.tmp')
        if isinstance(payload, str):
            payload = payload.encode('utf8')
        tmp.write_bytes(payload)
        tmp.chmod(mode)
        tmp.replace(dst)

    def copy(self, src, dst, mode=0o644):
        self.save(dst, Path(src).read_bytes(), mode)

    def manifest(self):
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.folder / 'manifest.json'
        path.write_text(json.dumps({'role': self.role, 'entries': self.entries,
                                    'units': self.units, 'container_created': self.container_created,
                                    'container_bridge': self.container_bridge}, indent=2) + '\n')
        path.chmod(0o600)
        STATE.mkdir(parents=True, exist_ok=True)
        return path

    def rollback(self, *, restore_units=True):
        if restore_units:
            for name in self.units:
                run(['systemctl', '--user', 'disable', '--now', name], check=False)
        for item in reversed(self.entries):
            path = Path(item['path'])
            if item['exists']:
                shutil.copy2(self.folder / item['backup'], path)
                path.chmod(item['mode'])
            else:
                path.unlink(missing_ok=True)
        if self.role == 'ubuntu' and self.container_bridge:
            bridge=self.container_bridge
            if bridge['old_exists']:
                run(['podman','cp',str(self.folder/'original-cdp-helper.js'),
                     bridge['container']+':/data/spotify-touch/cdp-helper.js'],check=False)
            elif not bridge.get('new_container'):
                run(['podman','exec','-u','0',bridge['container'],'rm','-f',
                     '/data/spotify-touch/cdp-helper.js'],check=False)
        if restore_units:
            run(['systemctl', '--user', 'daemon-reload'], check=False)
            for name, state in self.units.items():
                if state['enabled']:
                    run(['systemctl', '--user', 'enable', name], check=False)
                if state['active']:
                    run(['systemctl', '--user', 'start', name], check=False)


def user_unit(tx, name, content):
    tx.save(USER_UNITS / name, content)


def unit_ubuntu():
    return '''[Unit]
Description=SpotifyTouch local control API
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/.local/share/spotify-touch
EnvironmentFile=%h/.config/spotify-touch/ubuntu.env
ExecStart=/usr/bin/python3 %h/.local/share/spotify-touch/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
'''


def unit_ubuntu_container(name):
    return f'''[Unit]
Description=SpotifyTouch-managed Spotify Headless container
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/podman start --attach {name}
ExecStop=/usr/bin/podman stop -t 10 {name}
Restart=on-failure
RestartSec=5
TimeoutStopSec=20

[Install]
WantedBy=default.target
'''


def unit_pi_switch():
    return '''[Unit]
Description=SpotifyTouch local view and audio controller

[Service]
Type=simple
EnvironmentFile=%h/.config/spotify-touch/pi.env
ExecStart=/usr/bin/python3 %h/.local/share/spotify-touch/switchd.py
Restart=on-failure
RestartSec=3
TimeoutStopSec=8

[Install]
WantedBy=default.target
'''


def unit_pi_kiosk():
    return '''[Unit]
Description=SpotifyTouch persistent Electron kiosk viewer
Wants=spotify-touch-switch.service
After=spotify-touch-switch.service

[Service]
Type=simple
EnvironmentFile=%h/.config/spotify-touch/pi.env
ExecStart=%h/.local/share/spotify-touch/launch-viewer.sh
Restart=on-failure
RestartSec=5
TimeoutStopSec=15

[Install]
WantedBy=default.target
'''


def unit_pi_audio():
    return '''[Unit]
Description=SpotifyTouch on-demand audio consumer
After=pipewire-pulse.service

[Service]
Type=simple
EnvironmentFile=%h/.config/spotify-touch/pi.env
ExecStart=%h/.local/share/spotify-touch/launch-audio.sh
Restart=on-failure
RestartSec=3
# Intentionally no Install section. The controller starts/stops audio.
'''


def unit_pi_tunnel():
    return '''[Unit]
Description=SSH tunnel to Ubuntu SpotifyTouch control API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=%h/.config/spotify-touch/pi.env
ExecStart=%h/.local/share/spotify-touch/launch-tunnel.sh
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
'''


def env_file(items):
    for value in items.values():
        if re.search(r'[\n\r\"]', str(value)):
            fail('Invalid environment value')
    return ''.join(f'{key}="{value}"\n' for key, value in items.items())


def probe_http(url, timeout=4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except Exception:
        return None


def choose_confirmation(args, summary):
    print('\n=== PLAN (beta installer) ===')
    for line in summary:
        print(' - ' + line)
    print('No unrelated services or other Podman containers will be modified.')
    if args.dry_run:
        print('DRY RUN: no changes made.')
        return False
    if not (args.yes or yesno('Apply this configuration now?', noninteractive=False)):
        print('Cancelled. No changes made.')
        return False
    return True


def require_not_root():
    if os.geteuid() == 0:
        fail('Run as your normal user, not as root/sudo.')


def configure_ubuntu(args):
    if not args.dry_run: require_not_root()
    container = args.container or ask('Podman container name', 'spotify-headless', noninteractive=args.yes)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', container):
        fail('Unsafe container name')
    mode = args.container_mode
    if not mode:
        found = (shutil.which('podman') is not None and
                 run(['podman','container','exists',container],check=False).returncode == 0)
        recommended = '1' if found else '2'
        mode = ask('Use (1) existing Spotify Headless container or (2) create new one?',
                   recommended, noninteractive=args.yes)
        mode = {'1':'existing','2':'create'}.get(mode,mode)
    if mode not in ('existing', 'create'):
        fail('Container mode must be existing or create')
    image = args.image or 'ghcr.io/kk-spartans/spotify-headless:latest'
    if not re.fullmatch(r'[A-Za-z0-9._/:@-]+', image):
        fail('Unsafe image reference')
    port = args.stream_port
    if not (1024 <= port <= 65535):
        fail('Stream port out of range')
    summary = [f'Ubuntu control API: loopback 127.0.0.1:{CONTROL_PORT}',
               f'Container: {container} ({mode})',
               f'Spotify audio: host TCP port {port} -> container TCP 8080',
               f'Install to {APP_UBUNTU} and user systemd service spotify-touch-api.service',
               'Copy our CDP helper into the container mounted /data directory',
               'Back up overwritten files and enable API service',
               'Keep Spotify authentication/data inside the upstream container']
    if mode == 'create':
        summary.append('New container will have its own user systemd supervisor for reboot persistence')
        summary.append('CAUTION: new container login must be completed manually after setup')
        if image.endswith(':latest'):
            summary.append('CAUTION: upstream image uses mutable latest tag (not reproducible)')
    if not choose_confirmation(args, summary):
        return
    for tool in ('podman','systemctl','python3'):
        which(tool)
    if not ROOT.joinpath('src/ubuntu/server.py').exists():
        fail('Run the installer from a complete SpotifyTouch checkout')
    exists = run(['podman','container','exists',container],check=False).returncode == 0
    if mode == 'existing' and not exists:
        fail('Container not found. Start it, or choose create mode.')
    if mode == 'create' and exists:
        fail('Container already exists. Choose existing or a different container name.')
    if (USER_UNITS/'spotify-touch-api.service').exists():
        fail('Existing SpotifyTouch API deployment detected. Beta wizard supports fresh installs only; do not overwrite your working installation.')
    if mode == 'create' and os.uname().machine not in ('x86_64','amd64'):
        fail('Upstream Spotify Headless desktop image requires an x86-64 Linux host, not ARM64.')
    if mode == 'existing':
        state = run(['podman','inspect','-f','{{.State.Running}}',container],capture=True).stdout.strip()
        if state.lower() != 'true':
            fail('Existing Spotify Headless container must be running.')
    tx = Transaction('ubuntu', ['spotify-touch-api.service'] + (['spotify-touch-headless.service'] if mode == 'create' else []))
    created = False
    try:
        if mode == 'create':
            vol = f'spotifytouch-{container}-data'
            run(['podman', 'volume', 'create', vol])
            run(['podman', 'create', '--name', container,
                 '--shm-size=512m', '--tmpfs=/tmp:size=256m,mode=1777',
                 '-p', f'0.0.0.0:{port}:8080', '--security-opt=no-new-privileges',
                 '-v', f'{vol}:/data', '-e', 'AUTO_LOGIN_CLICK=true', image])
            created = True
            tx.container_created = container
            user_unit(tx,'spotify-touch-headless.service',unit_ubuntu_container(container))
            run(['systemctl','--user','daemon-reload'])
            run(['systemctl','--user','enable','--now','spotify-touch-headless.service'])
        if created:
            import time
            for _ in range(20):
                if run(['podman','exec',container,'true'],check=False).returncode == 0:
                    break
                time.sleep(1)
            else:
                fail('New Spotify Headless container did not become executable')
        # Back up the existing CDP bridge stored in the container's persistent /data.
        existing_bridge = run(['podman','exec',container,'test','-f',
                               '/data/spotify-touch/cdp-helper.js'],check=False).returncode == 0
        if existing_bridge:
            tx.folder.mkdir(parents=True,exist_ok=True)
            run(['podman','cp',f'{container}:/data/spotify-touch/cdp-helper.js',
                 str(tx.folder/'original-cdp-helper.js')])
        tx.container_bridge={'container':container,'old_exists':existing_bridge,'new_container':created}
        tx.manifest()
        run(['podman', 'exec', '-u', '0', container, 'mkdir', '-p', '/data/spotify-touch'])
        run(['podman','cp',str(ROOT/'src/ubuntu/cdp-helper.js'), f'{container}:/data/spotify-touch/cdp-helper.js'])
        tx.copy(ROOT/'src/ubuntu/server.py', APP_UBUNTU/'server.py')
        for path in sorted((ROOT/'src/ubuntu/web').iterdir()):
            if path.is_file():
                tx.copy(path, APP_UBUNTU/path.name)
        tx.save(CONFIG/'ubuntu.env', env_file({
            'SPOTIFY_CONTAINER_NAME':container,
            'SPOTIFY_BRIDGE_PATH':'/data/spotify-touch/cdp-helper.js',
            'SPOTIFY_TOUCH_PORT':str(CONTROL_PORT),
        }), mode=0o600)
        user_unit(tx,'spotify-touch-api.service',unit_ubuntu())
        tx.manifest()
        run(['systemctl','--user','daemon-reload'])
        run(['systemctl','--user','enable','--now','spotify-touch-api.service'])
        run(['systemctl','--user','restart','spotify-touch-api.service'])
        if probe_http(f'http://127.0.0.1:{CONTROL_PORT}/api?action=health',timeout=6) != 200:
            fail('Control API failed HTTP health check. See journalctl --user -u spotify-touch-api.service')
    except Exception:
        tx.rollback()
        if created:
            print(f'NOTE: New container {container} remains on the host; review manually before removal.', file=sys.stderr)
        raise
    (STATE/'last-ubuntu.json').write_text(json.dumps({'manifest':str(tx.manifest())})+'\n')
    print('\nUbuntu API installed and responding. Review:')
    print(f'  curl http://127.0.0.1:{CONTROL_PORT}/api?action=health')
    print(f'  Open http://<ubuntu-host>:{port}/ in a browser to complete Spotify login if needed.')
    print('  Keep the stream port restricted to a trusted LAN; do not expose it to the Internet.')
    if mode == 'create':
        print('  If the Ubuntu user must run services while logged out, enable user lingering:')
        print('  sudo loginctl enable-linger "$(whoami)"')
    print('  Rollback: bash scripts/rollback-ubuntu.sh')


def inject_magicmirror_module(config):
    if 'MMM-SpotifyTouch' in config:
        return config
    # Insert into the first top-level module list. MMM-pages has its own
    # nested "modules: [ ... ]" list, so counting both rejects valid dashboards.
    match = re.search(r'\bmodules\s*:\s*\[', config)
    if not match:
        fail('MagicMirror config needs a modules: [ declaration.')
    pos = match.end()
    return (config[:pos] +
            '\n    { module: "MMM-SpotifyTouch", position: "fullscreen_above", '
            'classes: "page-home spotify-touch-host" },' + config[pos:])


def configure_pi(args):
    if not args.dry_run: require_not_root()
    profile = args.profile
    if not profile:
        profile = ask('Mode: (1) Spotify-only kiosk or (2) MagicMirror companion?', '2', noninteractive=args.yes)
        profile = {'1':'standalone', '2':'companion'}.get(profile,profile)
    if profile not in ('standalone','companion'):
        fail('Choose standalone or companion')
    host = validate_host(args.ssh_host or ask('Ubuntu host/IP (no protocol or port)', None, noninteractive=args.yes))
    user = validate_user(args.ssh_user or ask('Ubuntu SSH username', getpass.getuser(), noninteractive=args.yes))
    key = validate_path(args.ssh_key or str(HOME/'.ssh/spotify_remote_ed25519'))
    mac = validate_mac(args.bluetooth_mac if args.bluetooth_mac is not None else
                       ask('Paired Bluetooth speaker MAC (leave empty for default audio)', '', noninteractive=args.yes))
    stream = validate_stream(args.audio_url or f'http://{host}:{args.stream_port}/spotify.ts')
    mm_dir = validate_path(args.magicmirror_dir or str(HOME/'MagicMirror'))
    if profile == 'companion':
        electron = validate_path(args.electron_bin or str(mm_dir/'node_modules/.bin/electron'))
    else:
        electron = validate_path(args.electron_bin or str(HOME/'.local/share/spotify-touch-electron/node_modules/.bin/electron'))
    summary = [f'Pi profile: {profile}', f'Ubuntu SSH API: {user}@{host}:127.0.0.1:{CONTROL_PORT}',
               f'SSH key stored locally: {key}', f'Audio stream: {stream}',
               f'Bluetooth device: {mac if mac else "none; use OS default output"}',
               f'Electron runtime: {electron}', 'Enable kiosk, switch, SSH tunnel user services; audio remains on demand',
               f'Kiosk state and services stored under {HOME}',
               'Minimal labwc/LightDM session is a separate, opt-in migration after testing']
    if profile == 'companion':
        summary.append(f'Back up and modify MagicMirror config and mm.sh under {mm_dir}')
    else:
        summary.append('Standalone Electron installation may be required; no MagicMirror needed')
    if not choose_confirmation(args, summary):
        return
    # A fresh-install wizard must not change the current appliance, including SSH keys.
    if (APP_PI/'switchd.py').exists() or (USER_UNITS/'spotify-touch-switch.service').exists():
        fail('Existing SpotifyTouch kiosk detected. This installer is for new setups only.')
    for tool in ('systemctl','ssh','python3','mpv','curl','labwc'):
        which(tool)
    if mac:
        for tool in ('bluetoothctl','wpctl'):
            which(tool)
    if profile == 'companion':
        for tool in ('pm2','node'):
            which(tool)
        if not (mm_dir/'installers/mm.sh').is_file() or not (mm_dir/'config/config.js').is_file():
            fail('MagicMirror not found. Check --magicmirror-dir and install MagicMirror first.')
        if not electron.exists():
            fail(f'MagicMirror Electron binary missing: {electron}')
        # Avoid the stale-PM2 definition that previously caused a reboot loop.
        state = run(['pm2','jlist'],capture=True)
        processes = [p for p in json.loads(state.stdout) if p.get('name')=='MagicMirror']
        if processes:
            if len(processes)!=1:
                fail('Expected exactly one MagicMirror PM2 process')
            e=processes[0].get('pm2_env',{})
            if (Path(e.get('pm_exec_path','')).resolve() != (mm_dir/'installers/mm.sh').resolve() or
                    Path(e.get('pm_cwd','')).resolve() != mm_dir.resolve()):
                fail('PM2 points to a stale launcher/cwd. Repair that first; installer will not overwrite PM2.')
    elif not electron.exists():
        which('npm')
        if args.yes and not args.install_electron:
            fail('Unattended standalone installation requires --install-electron or --electron-bin')
        if not (args.install_electron or yesno('Install isolated ARM64 Electron runtime with npm?',default=True)):
            fail('Standalone mode requires Electron; supply --electron-bin')
        run(['npm','install','--prefix',str(electron.parents[2]),'--no-audit','--no-fund','electron@38.0.0'])
        if not electron.exists():
            fail('Isolated Electron installation did not produce an executable')
    if not key.is_file():
        which('ssh-keygen')
        if not (args.setup_ssh or yesno('Create a dedicated SSH key?',default=True,noninteractive=args.yes)):
            fail('Dedicated SSH key is required for the tunnel')
        key.parent.mkdir(parents=True,exist_ok=True)
        run(['ssh-keygen','-t','ed25519','-N','','-f',str(key)])
    ssh_check = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',
                 '-o','StrictHostKeyChecking=yes','-i',str(key), f'{user}@{host}','true']
    if run(ssh_check,check=False).returncode:
        if not (args.setup_ssh or yesno('Run ssh-copy-id to authorize the key on Ubuntu now?', noninteractive=args.yes)):
            fail(f'SSH key not authorized or host key unknown. Run ssh-copy-id -i {key}.pub {user}@{host}, verify host key, then retry.')
        which('ssh-copy-id')
        run(['ssh-copy-id','-i',str(key)+'.pub', f'{user}@{host}'])
        run(ssh_check)
    if not Path('/usr/share/wayland-sessions/labwc.desktop').exists() and not Path('/usr/share/wayland-sessions/rpd-labwc.desktop').exists():
        fail('Pi needs a configured labwc/Wayland session. Install/enable labwc first.')
    unit_names = ['spotify-touch-switch.service','spotify-touch-kiosk.service',
                  'spotify-touch-audio.service','spotify-touch-tunnel.service']
    tx = Transaction('pi',unit_names)
    mm_launcher=mm_dir/'installers/mm.sh'
    marker=HOME/'.config/spotify-touch/enabled'
    try:
        for name in unit_names:
            run(['systemctl','--user','stop',name],check=False)
        for path in [ROOT/'src/pi/controller/switchd.py',ROOT/'src/pi/kiosk/electron-kiosk.js',ROOT/'src/pi/kiosk/launch-viewer.sh',
                     ROOT/'src/pi/kiosk/launch-audio.sh', ROOT/'src/pi/kiosk/launch-tunnel.sh']:
            tx.copy(path, APP_PI/path.name, 0o755 if path.suffix == '.sh' else 0o644)
        for path in ['minimal-session.sh','patch_launcher.py']:
            tx.copy(ROOT/'src/pi/session'/path, APP_PI/path, 0o755)
        tx.save(CONFIG/'pi.env',env_file({
            'SPOTIFY_KIOSK_MODE':'standalone' if profile=='standalone' else 'mirror',
            'SPOTIFY_BLUETOOTH_MAC':mac,
            'SPOTIFY_UBUNTU_HOST':host,
            'SPOTIFY_UBUNTU_USER':user,
            'SPOTIFY_SSH_IDENTITY_FILE':str(key),
            'SPOTIFY_AUDIO_PORT':str(args.stream_port),
            'SPOTIFY_AUDIO_URL_OVERRIDE':stream if args.audio_url else '',
            'SPOTIFY_ELECTRON_BIN':str(electron),
            'MAGICMIRROR_URL':'http://[::1]:8080/',
            'SPOTIFY_CONTROL_PORT':str(CONTROL_PORT),
            'SPOTIFY_SWITCH_PORT':str(SWITCH_PORT),
        }),0o600)
        user_unit(tx,'spotify-touch-switch.service',unit_pi_switch())
        user_unit(tx,'spotify-touch-kiosk.service',unit_pi_kiosk())
        user_unit(tx,'spotify-touch-audio.service',unit_pi_audio())
        user_unit(tx,'spotify-touch-tunnel.service',unit_pi_tunnel())
        if profile=='companion':
            mm_module=mm_dir/'modules/MMM-SpotifyTouch'
            for name in ['MMM-SpotifyTouch.js','MMM-SpotifyTouch.css','node_helper.js','spotify-glyph.svg']:
                tx.copy(ROOT/'src/pi/magicmirror'/name,mm_module/name)
            current=mm_dir.joinpath('config/config.js').read_text()
            amended=inject_magicmirror_module(current)
            if amended!=current:
                tx.save(mm_dir/'config/config.js',amended)
                run(['node','--check',str(mm_dir/'config/config.js')])
            current=mm_launcher.read_text()
            if '# spotify-touch: managed server-only branch' not in current:
                # Existing migration script has the exact guard we validated on the Pi.
                # It assumes MagicMirror at ~/MagicMirror. Non-default paths are not portable yet.
                if mm_dir != HOME/'MagicMirror':
                    fail('Non-default MagicMirror directory currently requires manual launcher integration.')
                sys.path.insert(0,str(ROOT/'src/pi/session'))
                from patch_launcher import patch_text
                tx.save(mm_launcher,patch_text(current),mm_launcher.stat().st_mode & 0o777)
            tx.save(marker,'',0o600)
        else:
            # standalone uses same marker as migration helper for optional lightdm session.
            tx.save(marker,'',0o600)
        tx.manifest()
        run(['systemctl','--user','daemon-reload'])
        run(['systemctl','--user','enable','--now','spotify-touch-tunnel.service'])
        run(['systemctl','--user','enable','--now','spotify-touch-switch.service'])
        if profile=='companion':
            # Preserve the registered PM2 process; never run electron.js through Node.
            existing = run(['pm2','jlist'],capture=True)
            matches=[p for p in json.loads(existing.stdout) if p.get('name')=='MagicMirror']
            if not matches:
                run(['pm2','start',str(mm_launcher),'--name','MagicMirror','--interpreter','bash'],cwd=mm_dir)
            else:
                run(['pm2','restart','MagicMirror'])
            ready=False
            for _ in range(60):
                if probe_http('http://[::1]:8080/',timeout=1)==200:
                    ready=True;break
                import time;time.sleep(1)
            if not ready:
                fail('MagicMirror server-only did not respond on IPv6 ::1:8080')
            run(['pm2','save'])
        run(['systemctl','--user','enable','--now','spotify-touch-kiosk.service'])
        ok=False
        for _ in range(90):
            if probe_http(f'http://127.0.0.1:{SWITCH_PORT}/health',timeout=1)==200:
                ok=True;break
            import time;time.sleep(1)
        if not ok:
            fail('Switch controller failed to start')
        # Do not mark a kiosk startup healthy until viewer heartbeat arrives.
        # This can wait for labwc to be available after graphical login.
        print('Viewer may take time to attach to Wayland; check /health viewer_alive after login.')
    except Exception:
        tx.rollback()
        if profile=='companion':
            run(['pm2','restart','MagicMirror'],check=False)
        raise
    (STATE/'last-pi.json').write_text(json.dumps({'manifest':str(tx.manifest())})+'\n')
    print('\nPi configuration installed. Check:')
    print(f'  curl http://127.0.0.1:{SWITCH_PORT}/health')
    print(f'  curl http://127.0.0.1:{CONTROL_PORT}/api?action=health')
    print('  systemctl --user status spotify-touch-tunnel.service spotify-touch-kiosk.service')
    print('  Enable minimal labwc only AFTER touch, Bluetooth and kiosk have been tested:')
    print(f'  bash {APP_PI}/minimal-session.sh --check')
    print(f'  bash {APP_PI}/minimal-session.sh --enable   # then reboot after confirming SSH access')
    print('  Rollback: bash scripts/rollback-pi.sh')


def rollback(role, args):
    require_not_root()
    index = STATE/f'last-{role}.json'
    if not index.is_file():
        fail(f'No recorded {role} installation to roll back')
    raw=json.loads(index.read_text())
    mf=Path(raw['manifest'])
    if not mf.is_file():
        fail('Backup manifest missing')
    obj=json.loads(mf.read_text())
    if obj['role']!=role:
        fail('Backup role mismatch')
    if not (args.yes or yesno(f"Restore {role} files/services from {mf.parent}?")):
        print('Cancelled')
        return
    tx = Transaction.__new__(Transaction)
    tx.role=role;tx.folder=mf.parent;tx.entries=obj['entries'];tx.units=obj['units']
    tx.container_bridge=obj.get('container_bridge')
    tx.rollback()
    if role=='pi' and shutil.which('pm2'):
        # A previous MagicMirror PM2 registration is not automatically deleted.
        run(['pm2','restart','MagicMirror'],check=False)
    index.unlink()
    print(f'{role} files and services restored. User data, SSH keys, container state and any OS session changes were preserved.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',choices=['ubuntu','pi','rollback-ubuntu','rollback-pi'])
    parser.add_argument('--dry-run',action='store_true',help='Print plan; do not modify anything')
    parser.add_argument('--yes',action='store_true',help='Use provided arguments/defaults; accept final confirmation')
    parser.add_argument('--container')
    parser.add_argument('--container-mode',choices=['existing','create'])
    parser.add_argument('--image')
    parser.add_argument('--profile',choices=['standalone','companion'])
    parser.add_argument('--ssh-host')
    parser.add_argument('--ssh-user')
    parser.add_argument('--ssh-key')
    parser.add_argument('--setup-ssh',action='store_true')
    parser.add_argument('--bluetooth-mac')
    parser.add_argument('--audio-url')
    parser.add_argument('--stream-port',type=int,default=18080)
    parser.add_argument('--magicmirror-dir')
    parser.add_argument('--electron-bin')
    parser.add_argument('--install-electron',action='store_true')
    args=parser.parse_args()
    if args.dry_run:
        args.yes=True
    try:
        if args.target=='ubuntu':configure_ubuntu(args)
        elif args.target=='pi':configure_pi(args)
        else:rollback(args.target.removeprefix('rollback-'),args)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(f'ERROR: {error}',file=sys.stderr)
        sys.exit(1)


if __name__=='__main__':main()