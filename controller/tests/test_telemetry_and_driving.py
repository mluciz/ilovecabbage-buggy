"""Unit tests do not require Bluetooth hardware or a display."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from motor_control import manual_wheels, brake_rate, approach_pwm, parse_telemetry
from ble_bridge import BLEBridge


class MotorControlTests(unittest.TestCase):
    def test_straight_wasd(self):
        self.assertEqual(manual_wheels({'W'}, 150, 0), (150, 150))
        self.assertEqual(manual_wheels({'S'}, 150, 90), (-150, -150))
        self.assertEqual(manual_wheels({'W', 'S'}, 150, 40), (0, 0))

    def test_steer_sensitivity_changes_inside_wheel_and_pivot(self):
        gentle = manual_wheels({'W', 'D'}, 150, 0)
        sharp = manual_wheels({'W', 'D'}, 150, 100)
        self.assertEqual(gentle[0], sharp[0])
        self.assertGreater(gentle[1], sharp[1])
        gentle_pivot = manual_wheels({'A'}, 150, 0)
        sharp_pivot = manual_wheels({'A'}, 150, 100)
        self.assertLess(abs(gentle_pivot[0]), abs(sharp_pivot[0]))

    def test_reverse_steer_and_clamping(self):
        self.assertEqual(manual_wheels({'S', 'A'}, 150, 50)[1], -150)
        self.assertEqual(manual_wheels({'W'}, 300, 150), (255, 255))

    def test_brake_strength_increases_deceleration(self):
        self.assertGreater(brake_rate(10), brake_rate(1))
        weak = approach_pwm(255, 0, brake_rate(1) * .08)
        strong = approach_pwm(255, 0, brake_rate(10) * .08)
        self.assertLess(strong, weak)
        self.assertEqual(approach_pwm(-10, 20, 100), 20)

    def test_telemetry_valid(self):
        t = parse_telemetry('T,-255,255,W,999\r')
        self.assertEqual((t.left_pwm, t.right_pwm, t.state, t.sequence),
                         (-255, 255, 'WATCHDOG BRAKE', 999))
        self.assertEqual(parse_telemetry('T,0,0,B,10').state, 'ACTIVE BRAKE')

    def test_telemetry_rejects_corruption(self):
        for line in ('M,120,120', 'T,256,0,D,0', 'T,1,1,X,1',
                     'T,1,2,B,1000', 'T,1,,D,1', 'T,1,1,C,0extra', ''):
            self.assertIsNone(parse_telemetry(line), line)

    def test_ble_notification_chunks(self):
        bridge = BLEBridge()
        bridge._notification(None, b'T,150,')
        self.assertTrue(bridge.events.empty())
        bridge._notification(None, b'140,D,1\nT,0,0,B,2\n')
        kind, value = bridge.events.get_nowait()
        self.assertEqual(kind, 'telemetry')
        self.assertEqual(value[0].left_pwm, 150)
        kind, value = bridge.events.get_nowait()
        self.assertEqual(kind, 'telemetry')
        self.assertEqual(value[0].state, 'ACTIVE BRAKE')


if __name__ == '__main__':
    unittest.main()
