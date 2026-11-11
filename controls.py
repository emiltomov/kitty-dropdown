import json
import os
from pathlib import Path
import subprocess


CLOSE = "× "


def state_file():
    directory = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return directory / "kitty-dropdown/controls.conf"


def session_file():
    return state_file().with_name("session.kitty")


class Controls:
    def __init__(self, manager):
        self.manager = manager
        self.original_mouse = manager.handle_tab_bar_mouse
        self.original_new_tab = manager.new_tab
        self.start = None
        self.pressed = None
        self.closable = set()
        self.tabs = None

    def save_session(self):
        from kitty.config import atomic_save
        from kitty.fast_data_types import NO_CLOSE_REQUESTED, current_application_quit_request
        from kitty.session import default_save_as_session_opts

        tabs = [(tab.id, len(tab) > 0) for tab in self.manager]
        # Save tab changes only; shutdown must not overwrite the session.
        if tabs == self.tabs or current_application_quit_request() != NO_CLOSE_REQUESTED:
            return
        self.tabs = tabs
        path = session_file()
        lines = self.manager.serialize_state_as_session(
            str(path), None, default_save_as_session_opts(), is_first=True
        )
        if lines:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_save(("\n".join(lines) + "\n").encode(), str(path))

    def new_tab(self, *args, **kwargs):
        from kitty.window import CwdRequest

        if not args and not kwargs:
            tab = self.manager.active_tab
            if tab is not None and tab.active_window is not None:
                kwargs["cwd_from"] = CwdRequest(tab.active_window)
        return self.original_new_tab(*args, **kwargs)

    def config(self):
        from kitty.fast_data_types import layer_shell_config_for_os_window

        return layer_shell_config_for_os_window(self.manager.os_window_id)

    def buttons(self):
        pinned = not self.config()["hide_on_focus_loss"]
        return (
            ("[Pin: on ]" if pinned else "[Pin: off]", "pin"),
            (" [-]", "smaller"),
            (" [+]", "larger"),
            (" [Reset]", "reset"),
        )

    def draw(self, data, screen, tab, before, max_length, index, is_last, extra):
        from kitty.tab_bar import draw_tab_with_separator

        labels = self.buttons()
        width = sum(len(label) for label, _ in labels) + 1
        self.start = screen.columns - width if screen.columns >= width + 10 else None
        available = max_length
        if self.start is not None:
            available = max(1, min(max_length, self.start - before))
        closable = tab.tab_id > 0 and available >= len(CLOSE) + 2
        if closable:
            available -= len(CLOSE)
        fg, bg = screen.cursor.fg, screen.cursor.bg
        end = draw_tab_with_separator(
            data, screen, tab, before, available, index, is_last, extra
        )
        if closable:
            # Insert before the native separator so it stays in the tab's extent.
            after = screen.cursor.x
            screen.cursor.x = end
            screen.insert_characters(len(CLOSE))
            screen.cursor.fg, screen.cursor.bg = fg, bg
            screen.draw(CLOSE)
            screen.cursor.fg = screen.cursor.bg = 0
            screen.cursor.x = after + len(CLOSE)
            end += len(CLOSE)
        if not extra.for_layout:
            if closable:
                self.closable.add(tab.tab_id)
            else:
                self.closable.discard(tab.tab_id)
        if is_last and self.start is not None and not extra.for_layout:
            # Kitty's trailing erase starts after the controls; clear title remnants.
            screen.erase_in_line(0, False)
            screen.cursor.x = self.start
            screen.cursor.fg = screen.cursor.bg = 0
            screen.cursor.bold = True
            screen.draw(" " + "".join(label for label, _ in labels))
            screen.cursor.bold = False
        return end

    def column_at(self, x, y):
        bar = self.manager.tab_bar
        geometry = bar.window_geometry
        if geometry.left <= x < geometry.right and geometry.top <= y < geometry.bottom:
            return (x - geometry.left) // bar.cell_width
        return None

    def close_at(self, x, y):
        column = self.column_at(x, y)
        if column is None:
            return None
        for extent in self.manager.tab_bar.tab_extents:
            if (
                extent.tab_id in self.closable
                and extent.x.end - len(CLOSE) <= column < extent.x.end
            ):
                return extent.tab_id
        return None

    def button_at(self, x, y):
        column = self.column_at(x, y)
        if self.start is None or column is None:
            return None
        start = self.start + 1
        for label, action in self.buttons():
            if start <= column < start + len(label):
                return action
            start += len(label)
        return None

    def mouse(self, x, y, button, modifiers, action):
        from kitty.fast_data_types import GLFW_MOUSE_BUTTON_LEFT, GLFW_PRESS, GLFW_RELEASE

        target = self.close_at(x, y) or self.button_at(x, y)
        if button == GLFW_MOUSE_BUTTON_LEFT:
            if action == GLFW_PRESS:
                self.pressed = target
                if target is not None:
                    return
            elif action == GLFW_RELEASE and self.pressed is not None:
                pressed, self.pressed = self.pressed, None
                if target == pressed:
                    if isinstance(target, int):
                        self.close(target)
                    else:
                        self.activate(target)
                return
        # Close glyphs belong to their tab; only their left clicks are intercepted.
        if target is None or isinstance(target, int):
            self.original_mouse(x, y, button, modifiers, action)

    def close(self, tab_id):
        from kitty.fast_data_types import get_boss

        tab = self.manager.tab_for_id(tab_id)
        if tab is not None:
            get_boss().close_tab(tab)

    def activate(self, action):
        from kitty.fast_data_types import (
            get_os_window_size, set_layer_shell_config,
        )
        from kitty.types import LayerShellConfig

        config = self.config()
        height = get_os_window_size(self.manager.os_window_id)["height"]
        if action == "pin":
            config["hide_on_focus_loss"] = not config["hide_on_focus_loss"]
        elif action == "reset":
            height = 929
        else:
            height = max(240, height + (100 if action == "larger" else -100))
        config["y_size_in_pixels"] = height
        config["y_size_in_cells"] = 1
        set_layer_shell_config(self.manager.os_window_id, LayerShellConfig(**config))
        path = state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"lines {height}px\n"
            f"hide_on_focus_loss {'yes' if config['hide_on_focus_loss'] else 'no'}\n"
        )
        self.place(height)
        self.manager.mark_tab_bar_dirty()

    def place(self, height=None):
        from kitty.fast_data_types import set_os_window_size, x11_window_id

        window_id = x11_window_id(self.manager.os_window_id)
        if window_id:
            height = height or self.config()["y_size_in_pixels"]
            result = subprocess.run(
                ["python3", str(Path(__file__).with_name("desktop.py"))],
                check=True, capture_output=True, text=True,
            )
            area = json.loads(result.stdout)
            if area is None:
                return
            x, y, width, maximum = area
            set_os_window_size(
                self.manager.os_window_id, width, min(max(240, height), maximum)
            )
            # Kitty's X11 panel placement currently uses the primary monitor.
            subprocess.Popen(
                ["wmctrl", "-i", "-r", hex(window_id), "-e", f"0,{x},{y},-1,-1"]
            )

    def focus(self, boss, window, data):
        if data["focused"]:
            self.place()


def on_tab_bar_dirty(boss, window, data):
    manager = data["tab_manager"]
    controls = getattr(manager, "_dropdown_controls", None)
    if controls is None:
        controls = manager._dropdown_controls = Controls(manager)
        manager.handle_tab_bar_mouse = controls.mouse
        manager.new_tab = controls.new_tab
    manager.tab_bar.draw_func = controls.draw
    for tab in manager:
        for child in tab:
            callbacks = child.watchers.on_focus_change
            if controls.focus not in callbacks:
                callbacks.append(controls.focus)
    controls.save_session()
