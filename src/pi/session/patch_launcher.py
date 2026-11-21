#!/usr/bin/env python3
"""Add a reversible server-only branch to the existing PM2 mm.sh launcher.

Do not change PM2's registered process, cwd, dump, or startup service.
"""
import os
from pathlib import Path
import sys

MARKER = '# spotify-appliance-v2-kiosk: managed server-only branch'
GUARD = '''# spotify-appliance-v2-kiosk: managed server-only branch
if [ -f "$HOME/.config/spotify-appliance-v2-kiosk/enabled" ]; then
  cd "$HOME/MagicMirror"
  exec node serveronly
fi
# end spotify-appliance-v2-kiosk branch
'''


def patch_text(original):
    if MARKER in original:
        raise ValueError('Launcher already patched by v2; restore first')
    if not original.startswith('#!'):
        raise ValueError('Cannot patch launcher without a shell shebang')
    first, rest = original.split('\n', 1)
    return first + '\n' + GUARD + rest


def main():
    path = Path(sys.argv[1])
    data = path.read_text()
    patched = patch_text(data)
    tmp = path.with_name(path.name + '.v2-temp')
    tmp.write_text(patched)
    os.chmod(tmp, path.stat().st_mode & 0o777)
    os.replace(tmp, path)


if __name__ == '__main__':
    main()