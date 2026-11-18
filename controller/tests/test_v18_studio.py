"""v1.8 UI/control/power regression tests. No physical Bluetooth or motor required."""
from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path

from app import BuggyApp
from operator_preferences import DEFAULTS, load_preferences, normalize, save_preferences
from power_path import explain_power_failure
from premium_visuals import command_label, clamp_pwm


def test_preferences_round_trip_and_never_persist_movement_commands():
    with tempfile.TemporaryDirectory() as directory:
        candidate = {
            "gear": 4, "precision": True, "steering": 27, "balance": -15,
            "gatt_uuid": "ffe1", "measured_speed_cm_s": "28.4",
            "wheel_spacing_cm": "13.5", "brake_latched": False,
            "running": True, "pressed": ["W"], "auto_connect": True,
            "motor_pwm": [255, 255], "device_address": "never_store",
        }
        path = save_preferences(candidate, directory)
        persisted = path.read_text(encoding="utf-8")
        saved = load_preferences(directory)
        assert path.is_file()
        assert saved == normalize(candidate)
        assert saved["gear"] == 4 and saved["gatt_uuid"] == "FFE1"
        for unsafe in ("brake_latched", "running", "pressed", "auto_connect",
                       "motor_pwm", "device_address"):
            assert unsafe not in persisted
        assert not Path(str(path) + ".tmp").exists()


def test_invalid_preferences_rejected_without_side_effects():
    with tempfile.TemporaryDirectory() as directory:
        bad = {"gear": True, "steering": 999, "balance": -999,
               "precision": "yes", "gatt_uuid": "../bad.txt",
               "measured_speed_cm_s": "-1", "wheel_spacing_cm": "NaN"}
        assert normalize(bad) == DEFAULTS
        path = save_preferences(bad, directory)
        assert load_preferences(directory) == DEFAULTS
        path.write_text("{ broken json", encoding="utf-8")
        assert load_preferences(directory) == DEFAULTS
        path.write_text("x" * 4097, encoding="utf-8")
        assert load_preferences(directory) == DEFAULTS


def test_power_triage_differentiates_usb_battery_and_logic_levels():
    report = explain_power_failure({
        "usb_ble": "ON", "battery_ble": "OFF",
        "battery_uno_led": "ON", "meter_3v3": "LOW / ZERO",
        "module_type": "BARE 3.3V MODULE", "common_ground": "OFF"})
    assert "CHANGE OF POWER SOURCE" in report
    assert "STOP: grounds are not confirmed common" in report
    assert "Do NOT move VCC to 5V" not in report or "Bare 3.3V" in report
    assert "Uno D3 TX is 5V logic" in report
    assert "No voltage measurement" not in report or "Manual observations" in report


def test_motor_canvas_labels_are_explicitly_commands():
    assert clamp_pwm(900) == 255
    assert clamp_pwm(-900) == -255
    assert command_label(0) == "BRAKE / 000"
    assert command_label(10) == "FWD  010"
    assert command_label(-150) == "REV  150"


class TestStudioTk:
    def setup_method(self):
        self.root = tk.Tk()
        self.app = BuggyApp(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        self.app._shutdown()
        self.root.update_idletasks()
        self.root.destroy()

    def test_three_workspaces_and_diagram_exist(self):
        assert set(self.app.pages) == {"drive", "routes", "system"}
        assert self.app._active_page == "drive"
        assert self.app.motor_visual.winfo_exists()
        assert self.app.link_visual.winfo_exists()
        assert self.app.route_left_canvas.winfo_exists()
        assert self.app.drive_pad_buttons["W"]
        self.app._navigate("routes")
        assert self.app._active_page == "routes"
        self.app._navigate("system")
        assert self.app._active_page == "system"
        self.app._redraw_link_visual()
        self.app._navigate("drive")
        self.app._redraw_drive_visual()
        assert self.app.motor_visual.find_all()

    def test_atomic_diagonal_pointer_press_and_release(self):
        self.app.online = True
        self.app.demo = False
        self.app.brake_latched = False
        self.app.bridge._emergency_latched = False
        sent = []
        self.app.bridge.set_motor = lambda l, r: sent.append(("M", l, r))
        self.app.bridge.set_brake = lambda: sent.append(("K",))
        self.app._press_combo(("W", "A"))
        assert self.app.pressed == {"W", "A"}
        assert len(sent) == 1
        left, right = self.app._manual_wheels()
        assert sent == [("M", left, right)]
        self.app._release_combo(("W", "A"))
        assert self.app.pressed == set()
        assert self.app.brake_latched
        assert sent[-1] == ("K",)

    def test_global_mouse_release_preserves_keyboard_held_direction(self):
        self.app.online = True
        self.app.demo = False
        self.app.bridge._emergency_latched = False
        self.app.bridge.set_motor = lambda l, r: None
        self.app.bridge.set_brake = lambda: None
        self.app._pressed_sources["W"].add("keyboard")
        self.app.pressed.add("W")
        self.app._press_combo(("W", "A"))
        assert self.app.pressed == {"W", "A"}
        self.app._clear_button_drive()
        assert self.app.pressed == {"W"}
        assert self.app._pressed_sources["W"] == {"keyboard"}
        assert self.app._pressed_sources["A"] == set()

    def test_page_change_fails_closed_without_stale_keys(self):
        self.app.demo_var.set(True)
        self.app.toggle_connection()
        self.app._press_combo(("W", "D"))
        assert self.app.pressed == {"W", "D"}
        self.app._navigate("system")
        assert not self.app.pressed
        assert self.app.brake_latched
        self.app._navigate("drive")
        assert not self.app.pressed

    def test_other_diagnostic_window_cannot_send_wasd(self):
        top = tk.Toplevel(self.root)
        target = tk.Label(top, text="Other modal")
        target.pack()
        class E:
            keysym = "w"
            char = "w"
            widget = target
        assert self.app._key_down(E()) == "break"
        assert not self.app.pressed
        top.destroy()

    def test_control_tuning_reset_never_arms_a_real_motor(self):
        self.app.steering_var.set(73)
        self.app.balance_var.set(21)
        self.app.precision_var.set(True)
        self.app.set_gear(4)
        self.app.reset_tuning()
        assert self.app.gear == DEFAULTS["gear"]
        assert self.app.steering_var.get() == DEFAULTS["steering"]
        assert self.app.balance_var.get() == DEFAULTS["balance"]
        assert not self.app.precision_var.get()
        assert self.app.brake_latched
