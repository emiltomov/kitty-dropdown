# Kitty dropdown

A native Kitty dropdown with **Ctrl+Esc** to show or hide the same terminal
session. It starts hidden at graphical login and hides when another window
receives focus. On GNOME X11, it follows the monitor containing the mouse
pointer. No `tdrop` is used.

## Features

- **Ctrl+Esc** toggles the existing terminal, preserving shells and tabs.
- Hidden startup at graphical login and automatic hiding on focus loss.
- Placement on the mouse pointer's monitor, including its usable width.
- Bottom tabs with a new-tab button, per-tab close buttons, pinning, and height controls.
- New tabs inherit the active shell's current directory.
- Translucent appearance, saved pin/height choices, and muted Kitty notifications.
- Optional per-user configuration without editing the checkout.

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

Create your optional per-user configuration from the example:

```sh
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/kitty-dropdown"
mkdir -p "$config_dir"
cp -n config.example.conf "$config_dir/config.conf"
```

Edit `$config_dir/config.conf`, for example:

```conf
lines 700px
background_opacity 0.85
hide_on_focus_loss no
kitty_override font_size=13
kitty_override cursor_shape=beam
kitty_override scrollback_lines=10000
kitty_override enable_audio_bell=no
```

`lines` sets the initial height in pixels. Opacity ranges from `0` (transparent)
to `1` (opaque). For pinning, `hide_on_focus_loss no` means **pin on**, while
`yes` means **pin off**. Other regular Kitty options, including fonts, colors,
scrollback, cursor style, and key mappings, use `kitty_override name=value`.
This configuration affects only the dropdown, not your normal Kitty windows.

The checked-in `quick-access-terminal.conf` provides these defaults:

| Setting | Value |
|---|---|
| Edge | Top |
| Height | `929px` (about 86% of a 1080p screen) |
| Background opacity | `0.74` |
| Hide on focus loss | `yes` |
| Tab bar | Bottom, visible with one tab |
| Monitor | Mouse pointer's monitor on GNOME X11 |
| New-tab directory | Active shell's current directory |
| Desktop notifications | Filtered; command-finish notifications disabled |

The bottom bar keeps the normal tabs and adds these clickable controls:

| Control | Action |
|---|---|
| `Pin` | Keep the dropdown visible when it loses focus; click again to restore auto-hide |
| `-` / `+` | Decrease/increase its height by 100 pixels |
| `Reset` | Restore the original 929-pixel height |
| `×` on each tab | Close that tab, asking first if Kitty's close confirmation applies |
| Native new-tab `+` beside the tabs | Open a shell tab in the active shell's directory |

Closing the last tab ends the dropdown session; the next **Ctrl+Esc** starts a
fresh one. Very narrow tabs omit `×`; middle-clicking a tab also closes it.

**Ctrl+Shift+T** also opens a tab in the active shell's current directory.
Changing directories with `cd` is reflected when opening the next tab. In a tab
with multiple shell panes, the active pane supplies the directory. Explicit
working directories in custom launch actions are preserved.

The first dropdown shell still starts in your home directory, regardless of
where `toggle` was invoked.

Pin and height choices persist in
`${XDG_STATE_HOME:-$HOME/.local/state}/kitty-dropdown/controls.conf`. Remove that
file to return to your configured initial height and pin state, or the checked-in
defaults when no user configuration exists.

Configuration precedence, from lowest to highest:

1. Checked-in `quick-access-terminal.conf`.
2. `${XDG_CONFIG_HOME:-$HOME/.config}/kitty-dropdown/config.conf`, if present.
3. Remembered bottom-bar height and pin choices in `controls.conf`.
4. Explicit launcher `--override` arguments.

To discard remembered choices after changing your initial height or pin state:

```sh
rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/kitty-dropdown/controls.conf"
```

The height is clamped between 240 pixels and the current monitor's usable height.
Ctrl+Esc still hides a pinned dropdown. On X11, showing it on another monitor
keeps the existing shell and tabs; the panel fits that monitor's usable width.
Placement is reapplied after every show request, even without a focus change.

Press **Ctrl+Esc** after editing the configuration to apply it to the existing
dropdown. Watcher Python code is cached by Kitty; after changing watcher hooks
in `controls.py` or `desktop.py`, exit the dropdown's shells normally and
recreate it to load the new code.
See the [native quick-access terminal reference](https://sw.kovidgoyal.net/kitty/kittens/quick-access-terminal/)
for supported settings.

To change the shortcut persistently, update the `binding` value in
`install-shortcut` and rerun it. GNOME Settings -> Keyboard -> Custom Shortcuts
can also change the current binding; rerunning the installer restores Ctrl+Esc.

## Troubleshooting

**The dropdown opens on the wrong monitor:** move the mouse pointer to the
desired monitor before pressing Ctrl+Esc. Monitor selection follows the pointer,
not the last focused application. The placement workaround is for GNOME X11;
Wayland monitor switching is not implemented. Check the detected usable area:

```sh
python3 desktop.py
```

**An edited initial height or pin setting does not take effect:** remembered
bar choices override the per-user configuration. Remove the saved controls file
described above and toggle again. `Reset` restores the built-in 929-pixel height
only; it does not change pinning or reload your configured initial height.

**The shortcut or login startup no longer works:** check that the portable Kitty
installation still exists at `~/.local/kitty.app`, then rerun `./install-shortcut`
from the current checkout. Installation is needed again after moving the
checkout, but not after ordinary configuration edits.

Startup runs after graphical login, when the GNOME display is available, not
before login. It does not install a system service or replace the system Kitty.

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
python3 -c 'from pathlib import Path; p = Path("install-shortcut"); compile(p.read_text(), str(p), "exec")'
python3 -m unittest discover -s tests -v
```

Run a single focused test:

```sh
python3 -m unittest discover -s tests -v -k hidden_autostart
```

For the bottom-bar controls and new-tab directory behavior:

```sh
python3 -m unittest discover -s tests -v -k ControlsTests
```

The tests use temporary files and an in-memory GSettings backend; they do not
change the desktop's real shortcuts or notification preferences.
