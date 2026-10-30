# Repository instructions

## Validation and desktop commands

Run these checks from the repository root; they do not launch a terminal or
modify desktop settings:

```sh
bash -n toggle
shellcheck toggle
python3 -c 'from pathlib import Path; p = Path("install-shortcut"); compile(p.read_text(), str(p), "exec")'
python3 -m unittest discover -s tests -v
```

Run just the installer/autostart test with:

```sh
python3 -m unittest discover -s tests -v -k hidden_autostart
python3 -m unittest discover -s tests -v -k ControlsTests
```

`tests/test_setup.py` exercises the executable scripts through subprocesses.
Launcher tests substitute a fake portable kitten under a temporary `HOME`;
installer tests use `GSETTINGS_BACKEND=memory` and a temporary `XDG_CONFIG_HOME`.
The latter launch a harmless stub through `Gio.DesktopAppInfo`, covering actual
desktop-entry argument handling, repeated installation, unrelated shortcuts,
and notification settings without changing the real desktop.

For a single manual toggle smoke test in a graphical desktop session, run
`./toggle` three times, returning focus to the dropdown before invoking it to
hide: the first invocation shows it, the second hides it, and the third restores
the same shell session. Clicking another window should also hide the dropdown.

Run `./install-shortcut` only when intentionally installing into the current
user's GNOME session. It registers Ctrl+Esc and hidden login startup, and
disables Kitty's GNOME notifications. Repeating installation must not duplicate
the shortcut registration or remove other custom shortcuts.

Runtime dependencies are Bash, Python 3 with PyGObject (`gi.repository.Gio`),
GNOME's media-key GSettings schemas, and a Kitty version supporting
`kitten quick-access-terminal` and global tab-bar watchers (tested with 0.49.2).
The X11 monitor helper also requires GTK 3 introspection and `wmctrl`.
The launcher expects Kitty's portable
installation at `~/.local/kitty.app/bin`, not the system Kitty executable.
Inspect native options with:

```sh
~/.local/kitty.app/bin/kitten quick-access-terminal --help
```

## Architecture

This is a user-level wrapper around Kitty's native quick-access terminal, not
a separate window-management implementation. The execution chain is:
GNOME custom shortcut -> `toggle` -> Kitty quick-access terminal ->
`quick-access-terminal.conf`.

`toggle` resolves the configuration relative to its own location, switches to
the user's home directory, and replaces itself with the detached native kitten.
The stable `--instance-group kitty-dropdown` makes repeated calls toggle the
existing terminal instead of creating independent terminals. Kitty owns the
terminal lifecycle and visibility state.

`install-shortcut` uses Gio.Settings to register an absolute, shell-quoted path
to `toggle`. It writes settings at a dedicated path using GNOME's relocatable
custom-keybinding schema and adds that path to the `custom-keybindings` array.
The binding is `<Control>Escape`. Because GNOME stores an absolute command path,
rerun the installer after moving the checkout.

The installer also writes an XDG autostart entry under the user's configuration
directory. It invokes `toggle --override start_as_hidden=yes` at graphical login;
normal shortcut invocations remain visible on first launch. Launcher arguments
are forwarded to the native kitten. Keep shell quoting for the GNOME shortcut
separate from desktop-entry escaping for the autostart `Exec` field.

Hidden startup is a launch-time override, not a global config default.
`./toggle --override start_as_hidden=yes` can preload the current session, but
another invocation still toggles an existing instance. Repeated installer runs
are idempotent; repeated launcher calls intentionally are not.

The configuration defines the Guake-style appearance: top edge, **929-pixel
height**, 0.74 opacity, hide on focus loss, no decorations, and an always-visible
bottom tab bar. The height is fixed in pixels, not dynamically calculated as a
monitor percentage.

`toggle` loads `controls.py` as a global Kitty watcher, scoped to this dropdown.
It augments native tab rendering and intercepts only control-button mouse
events; other tab events retain Kitty's handler. Pin changes native
`hide_on_focus_loss`; height changes use native OS-window resizing. Saved
choices in `$XDG_STATE_HOME/kitty-dropdown/controls.conf` (default
`~/.local/state/kitty-dropdown/controls.conf`) load after the base configuration
and optional `$XDG_CONFIG_HOME/kitty-dropdown/config.conf` (default
`~/.config/kitty-dropdown/config.conf`), and before explicit launcher overrides.
Keep this precedence: defaults, user configuration, saved controls, explicit
overrides. `config.example.conf` documents native settings without modifying a
user's existing configuration.

Bare native tab-bar `new_tab()` requests inherit the active window through
`CwdRequest`; explicit creation arguments remain unchanged. Ctrl+Shift+T uses
the native `new_tab_with_cwd` action. Keep the first shell's home directory
independent of this subsequent-tab behavior.

On initial focus and after every native show request, the watchers call
`desktop.py` with system Python to query the pointer monitor's usable geometry
through GDK. Its `on_load` hook wraps the native panel command handler, applying
placement after native visibility and configuration updates, and skips hidden
windows. Do not rely solely on focus callbacks: re-showing need not produce one.
Native Kitty sets the panel's size, and `wmctrl` positions that specific X11
window. This narrow workaround is needed because Kitty's native active-monitor
switching is macOS-only and its X11 panel placement uses the primary monitor.
Kitty still owns visibility and session lifecycle.

## Key conventions

- Keep the implementation native to Kitty; do not introduce `tdrop`. The
  portable installation is used without replacing the system Kitty or editing
  its normal user configuration.
- Preserve the launcher's environment isolation: prepend the portable `bin`
  directory to `PATH` and unset both `KITTY_INSTALLATION_DIR` and `KITTY_PID`.
  Otherwise a launch from an older Kitty can resolve kittens through the wrong
  installation.
- Resolve project resources relative to the script, independent of the calling
  directory. Preserve `cd "$HOME"` so new dropdown shells do not inherit an
  arbitrary checkout as their working directory.
- Keep the instance-group name, configuration `app_id`, and shortcut path
  identity stable unless intentionally migrating the dropdown. Changing the
  instance group creates a separate terminal; changing the shortcut path can
  leave the previous registration in GNOME.
- Scope appearance changes to `quick-access-terminal.conf`.
  `kitty_override` entries configure the dropdown's Kitty instance, while
  options such as `edge` and `hide_on_focus_loss` configure the quick-access
  terminal itself. Toggling reloads changed configuration without recreating
  the terminal. Watcher Python modules remain cached until the instance exits.
- Attach focus callbacks through window watchers, not
  `actions_on_focus_change`: Kitty treats windows with the latter callbacks as
  non-serializable UI windows when saving sessions. Keep control installation
  idempotent when the tab bar is marked dirty repeatedly.
- For autostart, preserve the `env` executable prefix and quoted launcher
  argument. Escape `%` as `%%` and shell-sensitive characters for the desktop
  `Exec` syntax, then let `GLib.KeyFile` handle the key-file escaping layer.
  The existing test deliberately uses a checkout path containing spaces,
  quotes, dollar signs, backticks, a percent sign, and a backslash.
- Notification suppression has two layers: the installer disables the
  `kitty` application's GNOME notifications, including existing Kitty windows;
  the config filters application notifications and disables command-finish
  notifications inside new dropdown instances. Keep other applications'
  GNOME notification settings unchanged.
- Preserve installer idempotency: batch the shortcut fields with
  `delay()` / `apply()`, append its path only if absent, retain unrelated paths,
  and flush writes with `Gio.Settings.sync()`. These are persistent desktop
  changes, so do not run the installer as a routine syntax check.

`README.md` documents installation, login startup, configuration, and removal.
