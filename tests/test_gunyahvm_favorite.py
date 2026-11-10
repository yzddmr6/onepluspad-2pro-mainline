#!/usr/bin/python3
"""Exercise the installed entry point against a real, isolated dconf backend."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
TREE = REPO / 'packaging/erhai-device-support/tree'
APP = 'io.github.yzddmr6.GunyahVM.desktop'
HELPER = TREE / 'usr/libexec/erhai/gunyahvm-favorite'

WORKER = r'''
import ast, subprocess, sys
from pathlib import Path
app, helper, action = sys.argv[1:]
base = ['firefox.desktop', 'org.gnome.Nautilus.desktop']
schema = 'io.github.yzddmr6.erhai.desktop'
def setting(*args):
    return subprocess.check_output(['gsettings', *args], text=True).strip()
def favorites():
    return ast.literal_eval(setting('get', 'org.gnome.shell', 'favorite-apps'))
if action == 'append':
    setting('set', 'org.gnome.shell', 'favorite-apps', repr(base))
    subprocess.run([helper], check=True)
    assert favorites() == base + [app]
    assert setting('get', schema, 'gunyahvm-favorite-added') == 'true'
elif action == 'present':
    original = [base[0], app, base[1]]
    setting('set', 'org.gnome.shell', 'favorite-apps', repr(original))
    subprocess.run([helper], check=True)
    assert favorites() == original
    assert setting('get', schema, 'gunyahvm-favorite-added') == 'true'
elif action == 'remove':
    assert favorites() == base + [app]
    setting('set', 'org.gnome.shell', 'favorite-apps', repr(base))
elif action == 'later-login':
    subprocess.run([helper], check=True)
    assert favorites() == base
    assert setting('get', schema, 'gunyahvm-favorite-added') == 'true'
else:
    raise ValueError(action)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell-schema', type=Path,
                        default=Path('/usr/share/glib-2.0/schemas/org.gnome.shell.gschema.xml'),
                        help='Actual GNOME Shell schema from the target distribution')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='erhai-favorite-') as tmp:
        root = Path(tmp)
        schemas = root / 'schemas'
        schemas.mkdir()
        shutil.copyfile(args.shell_schema, schemas / args.shell_schema.name)
        for path in (TREE / 'usr/share/glib-2.0/schemas').glob('*erhai.desktop.gschema.xml'):
            shutil.copyfile(path, schemas / path.name)
        subprocess.run(['glib-compile-schemas', '--strict', str(schemas)], check=True)
        data = root / 'data/applications'
        data.mkdir(parents=True)
        (data / APP).write_text('[Desktop Entry]\nType=Application\nName=GunyahVM\nExec=/usr/bin/true\n')

        def session(profile, action):
            home = root / profile
            home.mkdir(exist_ok=True)
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / 'config'),
                       XDG_CACHE_HOME=str(home / 'cache'), XDG_DATA_HOME=str(root / 'data'),
                       GSETTINGS_BACKEND='dconf', GSETTINGS_SCHEMA_DIR=str(schemas))
            subprocess.run(['dbus-run-session', '--', '/usr/bin/python3', '-c', WORKER,
                            APP, str(HELPER), action], env=env, check=True)
            assert (home / 'config/dconf/user').is_file(), 'No persistent dconf database'

        session('custom', 'append')
        print('PASS customized favorites appended, original order retained', flush=True)
        session('present', 'present')
        print('PASS existing favorite not duplicated or moved', flush=True)
        session('custom', 'remove')
        session('custom', 'later-login')
        print('PASS removal preserved across a new D-Bus session', flush=True)

        # Exercise the generator that GNOME uses, with the same entry except
        # for its executable's checkout location on this test host.
        autostart = root / 'generator-config/autostart'
        autostart.mkdir(parents=True)
        entry = (TREE / 'etc/xdg/autostart/erhai-gunyahvm-favorite.desktop').read_text()
        assert 'X-GNOME-Autostart-Phase' not in entry
        (autostart / 'erhai-gunyahvm-favorite.desktop').write_text(
            entry.replace('/usr/libexec/erhai/gunyahvm-favorite', str(HELPER)))
        outputs = [root / name for name in ('units', 'early', 'late')]
        for path in outputs:
            path.mkdir()
        env = dict(os.environ, XDG_CONFIG_HOME=str(autostart.parent),
                   XDG_CONFIG_DIRS=str(root / 'empty-config'),
                   XDG_CURRENT_DESKTOP='GNOME', SYSTEMD_LOG_LEVEL='warning')
        subprocess.run(['/usr/lib/systemd/user-generators/systemd-xdg-autostart-generator',
                        *map(str, outputs)], env=env, check=True)
        units = [unit for output in outputs for unit in output.glob('*.service')]
        assert len(units) == 1 and str(HELPER) in units[0].read_text(), units
        print('PASS systemd XDG autostart generator emits the migration service', flush=True)


if __name__ == '__main__':
    main()
