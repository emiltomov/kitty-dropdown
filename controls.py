import json
import os
from pathlib import Path
import subprocess


def state_file():
    directory = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return directory / "kitty-dropdown/controls.conf"


class Controls:
    def __init__(self, manager):
        self.manager = manager
        self.original_mouse = manager.handle_tab_bar_mouse
        self.original_new_tab = manager.new_tab
        self.start = None
        self.pressed = None

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
        end = draw_tab_with_separator(
            data, screen, tab, before, available, index, is_last, extra
        )
        if is_last and self.start is not None and not extra.for_layout:
            screen.cursor.x = self.start
            screen.cursor.fg = screen.cursor.bg = 0
            screen.cursor.bold = True
            screen.draw(" " + "".join(label for label, _ in labels))
            screen.cursor.bold = False
        return end

    def button_at(self, x, y):
        bar = self.manager.tab_bar
        geometry = bar.window_geometry
        if self.start is None or not (
            geometry.left <= x < geometry.right and geometry.top <= y < geometry.bottom
        ):
            return None
        column = (x - geometry.left) // bar.cell_width
        start = self.start + 1
        for label, action in self.buttons():
            if start <= column < start + len(label):
                return action
            start += len(label)
        return None

    def mouse(self, x, y, button, modifiers, action):
        from kitty.fast_data_types import GLFW_MOUSE_BUTTON_LEFT, GLFW_PRESS, GLFW_RELEASE

        target = self.button_at(x, y)
        if button == GLFW_MOUSE_BUTTON_LEFT:
            if action == GLFW_PRESS:
                self.pressed = target
            elif action == GLFW_RELEASE and self.pressed is not None:
                pressed, self.pressed = self.pressed, None
                if target == pressed:
                    self.activate(target)
                return
        if target is None:
            self.original_mouse(x, y, button, modifiers, action)

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
