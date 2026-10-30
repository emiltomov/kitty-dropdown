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
`kitten quick-access-terminal`. The launcher expects Kitty's portable
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
to `toggle`. It writes a dedicated relocatable custom-keybinding schema and
adds its path to GNOME's `custom-keybindings` array. The binding is
`<Control>Escape`. Because GNOME stores an absolute command path, rerun the
installer after moving the checkout.

The installer also writes an XDG autostart entry under the user's configuration
directory. It invokes `toggle --override start_as_hidden=yes` at graphical login;
normal shortcut invocations remain visible on first launch. Launcher arguments
are forwarded to the native kitten. Keep shell quoting for the GNOME shortcut
separate from desktop-entry escaping for the autostart `Exec` field.

The configuration defines the Guake-style appearance: top edge, **929-pixel
height**, 0.74 opacity, hide on focus loss, no decorations, and an always-visible
bottom tab bar. The height is fixed in pixels, not dynamically calculated as a
monitor percentage.

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
  terminal itself.
- Preserve installer idempotency: batch the shortcut fields with
  `delay()` / `apply()`, append its path only if absent, retain unrelated paths,
  and flush writes with `Gio.Settings.sync()`. These are persistent desktop
  changes, so do not run the installer as a routine syntax check.

`README.md` documents installation, login startup, configuration, and removal.
