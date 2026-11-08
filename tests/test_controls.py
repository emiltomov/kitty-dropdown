import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "controls.py"))
Controls = MODULE["Controls"]
DESKTOP = runpy.run_path(str(Path(__file__).resolve().parents[1] / "desktop.py"))


class Tab(list):
    def __init__(self, tab_id, *windows):
        super().__init__(windows)
        self.id = tab_id


class Manager(list):
    pass


class ControlsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, XDG_STATE_HOME=temporary.name)
        environment.start()
        self.addCleanup(environment.stop)
        self.path = Path(temporary.name) / "kitty-dropdown/controls.conf"
        self.config = {"hide_on_focus_loss": True, "y_size_in_pixels": 929}
        self.metrics = {"height": 929}
        self.boss = SimpleNamespace(close_tab=Mock())
        self.quit = 0
        self.save = Mock(side_effect=lambda data, path: Path(path).write_bytes(data))
        self.native = SimpleNamespace(
            GLFW_MOUSE_BUTTON_LEFT=0, GLFW_PRESS=1, GLFW_RELEASE=0,
            layer_shell_config_for_os_window=lambda _: dict(self.config),
            get_os_window_size=lambda _: self.metrics,
            set_layer_shell_config=lambda _, config: self.config.update(vars(config)),
            set_os_window_size=Mock(), x11_window_id=lambda _: 123,
            get_boss=lambda: self.boss,
            NO_CLOSE_REQUESTED=0, current_application_quit_request=lambda: self.quit,
        )
        modules = patch.dict(sys.modules, {
            "kitty": ModuleType("kitty"),
            "kitty.config": SimpleNamespace(atomic_save=self.save),
            "kitty.fast_data_types": self.native,
            "kitty.session": SimpleNamespace(default_save_as_session_opts=lambda: "defaults"),
            "kitty.types": SimpleNamespace(LayerShellConfig=SimpleNamespace),
            "kitty.window": SimpleNamespace(CwdRequest=lambda window: SimpleNamespace(window=window)),
        })
        modules.start()
        self.addCleanup(modules.stop)
        self.manager = SimpleNamespace(
            os_window_id=1, handle_tab_bar_mouse=Mock(), mark_tab_bar_dirty=Mock(),
            new_tab=Mock(), active_tab=SimpleNamespace(active_window=object()),
            tab_for_id=lambda tab_id: f"tab {tab_id}",
            serialize_state_as_session=Mock(return_value=[]),
            tab_bar=SimpleNamespace(
                window_geometry=SimpleNamespace(left=0, right=900, top=700, bottom=718),
                cell_width=9, tab_extents=(),
            ),
        )
        self.controls = Controls(self.manager)
        self.controls.start = 70

    def test_native_new_tab_inherits_the_current_window_each_time(self):
        for window in (object(), object()):
            self.manager.active_tab.active_window = window
            self.controls.new_tab()
            request = self.manager.new_tab.call_args.kwargs["cwd_from"]
            self.assertIs(request.window, window)

    def test_native_new_tab_preserves_explicit_requests_and_initial_directory(self):
        for args, kwargs in (
            ((), {"cwd_from": object()}),
            ((object(),), {}),
            ((), {"empty_tab": True}),
        ):
            with self.subTest(args=args, kwargs=kwargs):
                self.controls.new_tab(*args, **kwargs)
                self.manager.new_tab.assert_called_with(*args, **kwargs)
        self.manager.active_tab = None
        self.controls.new_tab()
        self.manager.new_tab.assert_called_with()

    def test_pin_click_saves_state_but_drag_off_does_not_activate(self):
        self.controls.place = Mock()
        self.controls.mouse(72 * 9, 710, 0, 0, 1)
        self.controls.mouse(72 * 9, 710, 0, 0, 0)
        self.assertFalse(self.config["hide_on_focus_loss"])
        self.assertIn("hide_on_focus_loss no", self.path.read_text())
        self.controls.place.assert_called_once_with(929)
        self.controls.mouse(72 * 9, 710, 0, 0, 1)
        self.controls.mouse(5, 710, 0, 0, 0)
        self.assertFalse(self.config["hide_on_focus_loss"])
        self.controls.mouse(5, 710, 0, 0, 1)
        self.controls.mouse(5, 710, 0, 0, 0)
        self.assertEqual(self.manager.handle_tab_bar_mouse.call_count, 2)

    def test_resize_uses_actual_height_with_a_minimum_and_reset(self):
        self.controls.place = Mock()
        self.metrics["height"] = 300
        self.controls.activate("smaller")
        self.assertEqual(self.config["y_size_in_pixels"], 240)
        self.metrics["height"] = 600
        self.controls.activate("larger")
        self.assertEqual(self.config["y_size_in_pixels"], 700)
        self.controls.activate("reset")
        self.assertIn("lines 929px", self.path.read_text())

    def test_monitor_placement_caps_height_and_targets_only_the_dropdown(self):
        result = SimpleNamespace(stdout="[1920, 29, 1920, 800]")
        with patch("subprocess.run", return_value=result), patch("subprocess.Popen") as move:
            self.controls.place()
        self.native.set_os_window_size.assert_called_once_with(1, 1920, 800)
        move.assert_called_once_with(
            ["wmctrl", "-i", "-r", "0x7b", "-e", "0,1920,29,-1,-1"]
        )

    def test_watcher_reinstallation_preserves_existing_focus_callbacks(self):
        callback = Mock()
        child = SimpleNamespace(watchers=SimpleNamespace(on_focus_change=[callback]))
        manager = Manager([Tab(1, child)])
        manager.__dict__.update(vars(self.manager))
        install = MODULE["on_tab_bar_dirty"]
        install(None, child, {"tab_manager": manager})
        install(None, child, {"tab_manager": manager})
        self.assertEqual(len(child.watchers.on_focus_change), 2)
        self.assertIs(child.watchers.on_focus_change[0], callback)
        self.assertIs(manager._dropdown_controls.original_new_tab, self.manager.new_tab)
        self.assertEqual(manager.new_tab, manager._dropdown_controls.new_tab)

    def test_tab_creation_and_closing_save_current_tabs_but_quitting_does_not(self):
        child = SimpleNamespace(watchers=SimpleNamespace(on_focus_change=[]))
        manager = Manager([Tab(1, child), Tab(2)])
        manager.__dict__.update(vars(self.manager))
        manager.serialize_state_as_session = lambda path, matched, options, is_first: [
            f"{path} {matched} {options} {is_first}",
            *(f"{tab.id}:{len(tab)}" for tab in manager),
        ]
        session = self.path.with_name("session.kitty")
        install = MODULE["on_tab_bar_dirty"]

        def dirty(*expected):
            install(None, child, {"tab_manager": manager})
            self.assertEqual(
                session.read_text().splitlines(),
                [f"{session} None defaults True", *expected],
            )

        dirty("1:1", "2:0")
        manager[1].append(child)
        dirty("1:1", "2:1")
        dirty("1:1", "2:1")
        self.assertEqual(self.save.call_count, 2)
        self.quit = 1
        manager[0].clear()
        dirty("1:1", "2:1")
        self.quit = 0
        dirty("1:0", "2:1")
        del manager[0]
        dirty("2:1")

    def test_controls_do_not_expand_the_last_tabs_clickable_extent(self):
        screen = SimpleNamespace(columns=100, cursor=SimpleNamespace(x=0, fg=0, bg=0))

        def draw_text(text):
            screen.cursor.x += len(text)

        def draw_tab(*args):
            screen.cursor.x = 12
            return 12

        screen.draw = draw_text
        screen.erase_in_line = lambda *args: None
        with patch.dict(sys.modules, {
            "kitty.tab_bar": SimpleNamespace(draw_tab_with_separator=draw_tab),
        }):
            for layout in (True, False):
                result = self.controls.draw(
                    None, screen, SimpleNamespace(tab_id=-1), 0, 100, 1, True,
                    SimpleNamespace(for_layout=layout),
                )
                self.assertEqual(result, 12)
                self.assertEqual(screen.cursor.x, 12 if layout else 100)

    def test_close_button_is_drawn_inside_each_real_tab_before_its_separator(self):
        class Screen:
            columns = 100

            def __init__(self):
                self.cursor = SimpleNamespace(x=0, fg=0, bg=0, bold=False)
                self.cells = ["x"] * self.columns

            def draw(self, text):
                for character in text:
                    self.cells[self.cursor.x] = character
                    self.cursor.x += 1

            def erase_in_line(self, how, private):
                self.cells[self.cursor.x:] = [" "] * (self.columns - self.cursor.x)

            def insert_characters(self, count):
                x = self.cursor.x
                self.cells[x:] = ([" "] * count + self.cells[x:])[:self.columns - x]

        def draw_tab(data, screen, tab, before, max_length, index, is_last, extra):
            screen.draw(tab.title[:max_length - 1] + " ")
            end = screen.cursor.x
            if not is_last:
                screen.draw("┇")
            return end

        screen = Screen()
        extra = SimpleNamespace(for_layout=False)
        with patch.dict(sys.modules, {
            "kitty.tab_bar": SimpleNamespace(draw_tab_with_separator=draw_tab),
        }):
            ends = [
                self.controls.draw(None, screen, SimpleNamespace(tab_id=tab_id, title=title),
                                   screen.cursor.x, 100, index, is_last, extra)
                for index, (tab_id, title, is_last) in enumerate(
                    ((1, "shell", False), (-1, "+", True)), 1
                )
            ]
            self.assertEqual("".join(screen.cells[:11]), "shell × ┇+ ")
            self.assertEqual("".join(screen.cells[11:73]).strip(), "")
            self.assertEqual(ends, [8, 11])
            self.assertEqual(self.controls.closable, {1})
            screen.cursor.x = 0
            self.controls.draw(None, screen, SimpleNamespace(tab_id=1, title="shell"),
                               0, 3, 1, False, extra)
            self.assertEqual(self.controls.closable, set())

    def test_close_click_closes_its_tab_while_other_tab_events_stay_native(self):
        extent = SimpleNamespace(tab_id=1, x=SimpleNamespace(start=0, end=8))
        self.manager.tab_bar.tab_extents = (extent,)
        self.controls.closable = {1}
        close, title = 6 * 9, 2 * 9
        self.controls.mouse(close, 710, 0, 0, 1)
        self.controls.mouse(close, 710, 0, 0, 0)
        self.boss.close_tab.assert_called_once_with("tab 1")
        self.controls.mouse(close, 710, 0, 0, 1)
        self.controls.mouse(title, 710, 0, 0, 0)
        self.controls.mouse(close, 710, 2, 0, 1)
        self.controls.mouse(close, 710, 2, 0, 0)
        self.controls.mouse(title, 710, 0, 0, 1)
        self.controls.mouse(close, 710, 0, 0, 0)
        self.boss.close_tab.assert_called_once()
        self.assertEqual(self.manager.handle_tab_bar_mouse.call_count, 4)


class MonitorTests(unittest.TestCase):
    def test_every_show_places_after_native_toggle_without_focus_callbacks(self):
        calls = []
        original = Mock(spec=[], side_effect=lambda *args, **kwargs: calls.append("native"))
        panel = SimpleNamespace(handle_single_instance_command=original)
        controls = SimpleNamespace(place=lambda: calls.append("place"))
        manager = SimpleNamespace(os_window_id=1, _dropdown_controls=controls)
        boss = SimpleNamespace(os_window_map={1: manager})
        with patch.dict(sys.modules, {
            "kittens.panel": SimpleNamespace(main=panel),
            "kitty.fast_data_types": SimpleNamespace(os_window_is_invisible=lambda _: False),
        }):
            DESKTOP["on_load"](boss, {})
            handler = panel.handle_single_instance_command
            DESKTOP["on_load"](boss, {})
            self.assertIs(panel.handle_single_instance_command, handler)
            for _ in range(2):
                handler(boss, ["panel"], {}, notify_on_os_window_death="socket")
        self.assertEqual(calls, ["native", "place", "native", "place"])
        original.assert_called_with(
            boss, ["panel"], {}, notify_on_os_window_death="socket"
        )

    def test_hidden_and_unrelated_windows_are_not_repositioned(self):
        visible, hidden = SimpleNamespace(place=Mock()), SimpleNamespace(place=Mock())
        boss = SimpleNamespace(os_window_map={
            1: SimpleNamespace(os_window_id=1, _dropdown_controls=visible),
            2: SimpleNamespace(os_window_id=2, _dropdown_controls=hidden),
            3: SimpleNamespace(os_window_id=3),
        })
        panel = SimpleNamespace(
            handle_single_instance_command=Mock(spec=[], return_value="result")
        )
        with patch.dict(sys.modules, {
            "kittens.panel": SimpleNamespace(main=panel),
            "kitty.fast_data_types": SimpleNamespace(os_window_is_invisible=lambda i: i == 2),
        }):
            DESKTOP["on_load"](boss, {})
            self.assertEqual(panel.handle_single_instance_command(boss, [], {}), "result")
        visible.place.assert_called_once_with()
        hidden.place.assert_not_called()


if __name__ == "__main__":
    unittest.main()
