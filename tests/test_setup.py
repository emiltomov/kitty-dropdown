import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def test_launcher_forwards_hidden_start_without_changing_normal_toggle(self):
        with tempfile.TemporaryDirectory() as home:
            kitten = Path(home) / ".local/kitty.app/bin/kitten"
            kitten.parent.mkdir(parents=True)
            kitten.write_text(
                "#!/bin/bash\n"
                '[[ $PWD == "$HOME" ]] || exit 1\n'
                "[[ ! ${KITTY_PID+x} && ! ${KITTY_INSTALLATION_DIR+x} ]] || exit 1\n"
                "printf '%s\\n' \"$@\"\n"
            )
            kitten.chmod(0o755)
            env = dict(os.environ, HOME=home, KITTY_PID="123", KITTY_INSTALLATION_DIR="/old")
            for arguments in ([], ["--override", "start_as_hidden=yes"]):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [str(ROOT / "toggle"), *arguments],
                        env=env, check=True, capture_output=True, text=True,
                    )
                    self.assertEqual(
                        result.stdout.splitlines(),
                        [
                            "quick-access-terminal", "--config",
                            str(ROOT / "quick-access-terminal.conf"),
                            "--instance-group", "kitty-dropdown",
                            *arguments, "--detach",
                        ],
                    )

    def test_install_preserves_shortcuts_and_creates_hidden_autostart(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config"
            project = Path(temporary) / 'checkout with "quotes" $cash `tick` % \\slash'
            project.mkdir()
            installer = project / "install-shortcut"
            installer.write_text((ROOT / "install-shortcut").read_text())
            launcher = project / "toggle"
            launcher.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                'Path(__file__).with_name("launched.json").write_text(json.dumps(sys.argv[1:]))\n'
            )
            launcher.chmod(0o755)
            result = subprocess.run(
                ["python3", "-c", """
import json
import runpy
import shlex
import sys
import time
from pathlib import Path
from gi.repository import Gio

installer = Path(sys.argv[1])
settings = Gio.Settings.new("org.gnome.settings-daemon.plugins.media-keys")
other = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/other/"
settings.set_strv("custom-keybindings", [other])
runpy.run_path(str(installer))
runpy.run_path(str(installer))
paths = settings.get_strv("custom-keybindings")
assert len(paths) == 2 and paths[0] == other, paths
shortcut = Gio.Settings.new_with_path(
    "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding", paths[1]
)
assert shortcut.get_string("binding") == "<Control>Escape"
assert shlex.split(shortcut.get_string("command")) == [str(installer.parent / "toggle")]
entry = Gio.DesktopAppInfo.new_from_filename(sys.argv[2])
assert entry is not None, "Invalid autostart desktop entry"
entry.launch([], None)
marker = installer.parent / "launched.json"
deadline = time.monotonic() + 5
while not marker.exists() and time.monotonic() < deadline:
    time.sleep(0.02)
assert json.loads(marker.read_text()) == ["--override", "start_as_hidden=yes"]
notifications = Gio.Settings.new_with_path(
    "org.gnome.desktop.notifications.application",
    "/org/gnome/desktop/notifications/application/kitty/",
)
assert not notifications.get_boolean("enable")
""", str(installer), str(config / "autostart/kitty-dropdown.desktop")],
                env=dict(os.environ, GSETTINGS_BACKEND="memory", XDG_CONFIG_HOME=str(config)),
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
