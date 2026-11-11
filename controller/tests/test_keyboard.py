"""Integration tests for Tk keyboard input (requires a display or xvfb-run)."""
import sys
import tkinter as tk
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import BuggyApp


class KeyboardTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = BuggyApp(self.root)
        self.root.update()
        self.app.demo_var.set(True)
        self.app.toggle_connection()
        self.root.update()
        self.assertTrue(self.app.demo)
        self.assertTrue(self.app.online)

    def tearDown(self):
        self.app._shutdown()
        self.root.destroy()

    def send(self, widget, kind, key):
        self.root.update()
        widget.event_generate(kind, keysym=key)
        self.root.update()

    def test_wasd_changes_display_instantly_and_releases(self):
        self.app.activate_keyboard()
        self.root.update()
        self.send(self.app.drive_panel, '<KeyPress>', 'w')
        self.assertEqual(self.app.pressed, {'W'})
        self.assertIn('L +255', self.app.command_var.get())
        self.assertIn('R +255', self.app.command_var.get())
        self.assertIn('W', self.app.keys_var.get())
        self.send(self.app.drive_panel, '<KeyRelease>', 'w')
        time.sleep(0.09)
        self.root.update()
        self.assertFalse(self.app.pressed)
        self.assertIn('none', self.app.keys_var.get())
        self.assertIn('L   +0', self.app.command_var.get())

    def test_windows_key_autorepeat_does_not_interrupt_drive(self):
        self.app.activate_keyboard()
        self.send(self.app.drive_panel, '<KeyPress>', 'w')
        for _ in range(6):
            self.send(self.app.drive_panel, '<KeyRelease>', 'w')
            self.send(self.app.drive_panel, '<KeyPress>', 'w')
            time.sleep(0.025)
            self.root.update()
            self.assertIn('W', self.app.pressed)
        self.send(self.app.drive_panel, '<KeyRelease>', 'w')
        time.sleep(0.09)
        self.root.update()
        self.assertFalse(self.app.pressed)

    def test_gear_hotkeys_and_clicks(self):
        self.app.activate_keyboard()
        self.root.update()
        self.send(self.app.drive_panel, '<KeyPress>', '4')
        self.assertEqual(self.app.gear, 4)
        self.assertIn('GEAR 4', self.app.gear_info_var.get())
        self.app.gear_buttons[1].invoke()
        self.assertEqual(self.app.gear, 1)
        self.assertIn('GEAR 1', self.app.gear_info_var.get())

    def test_editing_field_ignores_manual_control_but_reports_why(self):
        self.app.activate_keyboard()
        self.root.update()
        # When a track field is focused, keyboard controls must be disabled.
        self.app.custom_text.focus_set()
        self.root.update()
        self.send(self.app.custom_text, '<KeyPress>', 'w')
        self.assertFalse(self.app.pressed)
        self.assertIn('ignored', self.app.last_input_var.get())
        self.app.activate_keyboard()
        self.send(self.app.drive_panel, '<KeyPress>', 'w')
        self.assertEqual(self.app.pressed, {'W'})

    def test_demo_button_press_immediately_updates_state(self):
        self.app._press('D')
        self.assertIn('D', self.app.keys_var.get())
        self.assertIn('GEAR 2', self.app.command_var.get())
        self.app._release('D')
        self.assertFalse(self.app.pressed)


if __name__ == '__main__':
    unittest.main()
