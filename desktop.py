from functools import wraps
import json


def monitor_geometry():
    import gi

    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    if display is None:
        return None
    pointer = display.get_default_seat().get_pointer()
    _, x, y = pointer.get_position()
    monitor = display.get_monitor_at_point(x, y)
    if monitor is None:
        return None
    area = monitor.get_workarea()
    return area.x, area.y, area.width, area.height


def on_load(boss, data):
    from kittens.panel import main as panel
    from kitty.fast_data_types import os_window_is_invisible

    original = panel.handle_single_instance_command
    if getattr(original, "_kitty_dropdown_monitor", False):
        return

    @wraps(original)
    def handle(boss, *args, **kwargs):
        result = original(boss, *args, **kwargs)
        # Native X11 show/config reload restores primary-monitor placement.
        for manager in boss.os_window_map.values():
            controls = getattr(manager, "_dropdown_controls", None)
            if controls is not None and not os_window_is_invisible(manager.os_window_id):
                controls.place()
        return result

    handle._kitty_dropdown_monitor = True
    panel.handle_single_instance_command = handle


if __name__ == "__main__":
    print(json.dumps(monitor_geometry()))
