# Kitty dropdown

A native Kitty dropdown with **Ctrl+Esc** to show or hide the same terminal
session. It starts hidden at graphical login and hides when another window
receives focus. No `tdrop` is used.

## Install

Requires a GNOME desktop session, Bash, Python 3 with PyGObject, and a Kitty
version that supports `kitten quick-access-terminal`.

On Ubuntu, install the Python integration if needed:

```sh
sudo apt install python3-gi gir1.2-glib-2.0
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

Use native quick-access options such as `lines 600px` or
`hide_on_focus_loss no`. Prefix regular Kitty settings with `kitty_override`,
for example `kitty_override font_size=12`.

Configuration is applied when a new dropdown instance starts. To apply changes,
exit its shells normally, then press **Ctrl+Esc** to recreate it.
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

The tests use temporary files and an in-memory GSettings backend; they do not
change the desktop's real shortcuts or notification preferences.
