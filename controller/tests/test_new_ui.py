"""Tkinter interaction integration (run under xvfb-run outside Windows)."""
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import BuggyApp


class UIControlTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = BuggyApp(self.root)
        self.root.update()
        self.app.demo_var.set(True)
        self.app.toggle_connection()
        self.root.update()

    def tearDown(self):
        self.app._shutdown()
        self.root.destroy()

    def pulse(self):
        # Tests call the tick synchronously; remove its pending scheduled copy.
        if self.app._tick_after:
            self.root.after_cancel(self.app._tick_after)
            self.app._tick_after = None
        self.app._tick()

    def test_adjustable_steering_changes_wheel_target(self):
        self.app._press('W')
        self.app._press('D')
        self.app.steering_var.set(0)
        gentle = self.app._manual_wheels()
        self.app.steering_var.set(100)
        sharp = self.app._manual_wheels()
        self.assertGreater(gentle[1], sharp[1])

    def test_release_latches_active_brake_without_coasting(self):
        self.app._press('W')
        self.app._last_tick_at -= .1
        self.pulse()
        before = self.app.applied_left
        self.assertGreater(before, 0)
        self.app._release('W')
        self.app._last_tick_at -= .08
        self.pulse()
        self.assertGreaterEqual(before, self.app.applied_left)
        self.assertEqual(self.app.applied_left, 0)
        self.assertEqual(self.app.applied_right, 0)
        self.assertTrue(self.app.brake_latched)
        self.assertIn('ACTIVE BRAKE', self.app.drive_state_var.get())

    def test_emergency_brake_latches_until_new_motion(self):
        self.app._press('W')
        self.app._last_tick_at -= .1
        self.pulse()
        self.app.emergency_stop()
        self.assertTrue(self.app.brake_latched)
        self.assertEqual(self.app.applied_left, 0)
        self.app._last_tick_at -= .1
        self.pulse()
        self.assertIn('ACTIVE BRAKE', self.app.drive_state_var.get())
        self.app._press('W')  # stale repeat must not restart after emergency brake
        self.assertTrue(self.app.brake_latched)
        self.app._key_up(type('Event', (), {'keysym': 'w', 'char': 'w'})())
        time.sleep(0.09)
        self.root.update()
        self.app._press('W')
        self.assertFalse(self.app.brake_latched)

    def test_demo_does_not_claim_real_arduino_feedback(self):
        self.app._press('A')
        self.app._last_tick_at -= .1
        self.pulse()
        self.assertIn('SIMULATED', self.app.telemetry_pwm_var.get())
        self.assertIn('NO BLE', self.app.telemetry_link_var.get())

    def test_telemetry_display_responds_to_ble_events(self):
        from motor_control import MotorTelemetry
        self.app.demo = False
        self.app.bridge.events.put(('telemetry', (MotorTelemetry(120, -30, 'DRIVE', 14), time.monotonic())))
        self.pulse()
        self.assertIn('L +120', self.app.telemetry_pwm_var.get())
        self.assertIn('LIVE REPLIES', self.app.telemetry_link_var.get())


if __name__ == '__main__':
    unittest.main()
