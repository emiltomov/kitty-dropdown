# Kitty dropdown

A native Kitty dropdown with **Ctrl+Esc** to show or hide the same terminal
session. It starts hidden at graphical login and hides when another window
receives focus. On GNOME X11, it follows the monitor containing the mouse
pointer. No `tdrop` is used.

## Install

Requires a GNOME desktop session, Bash, Python 3 with PyGObject, and a Kitty
version that supports `kitten quick-access-terminal` and global tab-bar watchers
(tested with Kitty 0.49.2). Monitor placement also uses GTK 3 introspection and
`wmctrl` on X11.

On Ubuntu, install the Python integration if needed:

```sh
sudo apt install python3-gi gir1.2-glib-2.0 gir1.2-gtk-3.0 wmctrl
```

Install the official portable Kitty release at `~/.local/kitty.app`:

```sh
curl -L https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin launch=n
```

This leaves the system Kitty installation unchanged. From this checkout, run:

```sh
./install-shortcut
./toggle --override start_as_hidden=yes
```

The installer registers **Ctrl+Esc**, creates
`${XDG_CONFIG_HOME:-~/.config}/autostart/kitty-dropdown.desktop`, and disables
GNOME notifications for Kitty only. Existing custom shortcuts are preserved.
The second command preloads the terminal for the current session; at subsequent
graphical logins, the desktop starts it automatically. Run that command only
once per session: invoking the launcher again toggles the existing terminal.

Keep the checkout in place. If you move it, rerun `./install-shortcut` to update
the shortcut and autostart paths.

## Configure

Edit `quick-access-terminal.conf`. Current settings:

| Setting | Value |
|---|---|
| Edge | Top |
| Height | `929px` (about 86% of a 1080p screen) |
| Background opacity | `0.74` |
| Hide on focus loss | `yes` |
| Tab bar | Bottom, visible with one tab |
| Desktop notifications | Filtered; command-finish notifications disabled |

The bottom bar keeps the normal tabs and adds these clickable controls:

| Control | Action |
|---|---|
| `Pin` | Keep the dropdown visible when it loses focus; click again to restore auto-hide |
| `-` / `+` | Decrease/increase its height by 100 pixels |
| `Reset` | Restore the original 929-pixel height |
| Native new-tab `+` beside the tabs | Open another shell tab |

Pin and height choices persist in
`${XDG_STATE_HOME:-$HOME/.local/state}/kitty-dropdown/controls.conf`. Remove that
file to return to the checked-in defaults. Saved choices override the base
configuration; explicit launcher `--override` arguments take precedence.
The height is capped at the current monitor's usable area.
Ctrl+Esc still hides a pinned dropdown. On X11, showing it on another monitor
keeps the existing shell and tabs; the panel fits that monitor's usable width.
Placement is reapplied after every show request, even without a focus change.

Use native quick-access options such as `lines 600px` or
`hide_on_focus_loss no`. Prefix regular Kitty settings with `kitty_override`,
for example `kitty_override font_size=12`.

Press **Ctrl+Esc** after editing the configuration to apply it to the existing
dropdown. Watcher Python code is cached by Kitty; after changing watcher hooks
in `controls.py` or `desktop.py`, exit the dropdown's shells normally and
recreate it to load the new code.
See the [native quick-access terminal reference](https://sw.kovidgoyal.net/kitty/kittens/quick-access-terminal/)
for supported settings.

To change the shortcut persistently, update the `binding` value in
`install-shortcut` and rerun it. GNOME Settings -> Keyboard -> Custom Shortcuts
can also change the current binding; rerunning the installer restores Ctrl+Esc.

## Disable or remove

To stop login startup, remove only its desktop entry:

```sh
rm "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/kitty-dropdown.desktop"
```

Remove **Kitty dropdown** from GNOME Settings -> Keyboard -> Custom Shortcuts
to disable the shortcut. Close the dropdown's shells normally to stop it.
To re-enable Kitty notifications in GNOME:

```sh
gsettings set org.gnome.desktop.notifications.application:/org/gnome/desktop/notifications/application/kitty/ enable true
```

To allow notifications inside future dropdown instances too, remove the
`filter_notification` and `notify_on_cmd_finish` overrides from the configuration.
Rerunning `./install-shortcut` reinstates startup, Ctrl+Esc, and muted notifications.

## Validate

```sh
bash -n toggle
shellcheck toggle
python3 -m unittest discover -s tests -v
```

Run a single focused test:

```sh
python3 -m unittest discover -s tests -v -k hidden_autostart
```

For the bottom-bar controls:

```sh
python3 -m unittest discover -s tests -v -k ControlsTests
```

The tests use temporary files and an in-memory GSettings backend; they do not
change the desktop's real shortcuts or notification preferences.
