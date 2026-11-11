import unittest
from controller.motion import mix, packet


class MotionTests(unittest.TestCase):
    def test_forward_reverse(self):
        self.assertEqual(mix({"w"}, 170), (170, 170))
        self.assertEqual(mix({"s"}, 170), (-170, -170))

    def test_stopped(self):
        self.assertEqual(mix(set(), 170), (0, 0))
        self.assertEqual(mix({"w", "s"}, 170), (0, 0))
        self.assertEqual(mix({"w", "s", "a"}, 170), (0, 0))
        self.assertEqual(mix({"a", "d"}, 170), (0, 0))

    def test_pivots(self):
        self.assertEqual(mix({"a"}, 180), (-180, 180))
        self.assertEqual(mix({"d"}, 180), (180, -180))

    def test_forward_arcs(self):
        self.assertEqual(mix({"w", "a"}, 200), (110, 200))
        self.assertEqual(mix({"w", "d"}, 200), (200, 110))

    def test_reverse_arcs(self):
        self.assertEqual(mix({"s", "a"}, 200), (-200, -110))
        self.assertEqual(mix({"s", "d"}, 200), (-110, -200))

    def test_limits(self):
        for speed in range(256):
            for keys in (set(), {"w"}, {"s"}, {"a"}, {"d"},
                         {"w", "a"}, {"w", "d"}, {"s", "a"}, {"s", "d"}):
                l, r = mix(keys, speed)
                self.assertTrue(-255 <= l <= 255)
                self.assertTrue(-255 <= r <= 255)
                self.assertLessEqual(abs(l), speed)
                self.assertLessEqual(abs(r), speed)
        for invalid in (-1, 256):
            with self.assertRaises(ValueError):
                mix({"w"}, invalid)

    def test_frame(self):
        self.assertEqual(packet(-255, 255), b"M,-255,255\n")
        self.assertEqual(packet(0, 0), b"M,0,0\n")
        for x in (-256, 256, 0.5, "1", True):
            with self.assertRaises(ValueError):
                packet(x, 0)


if __name__ == "__main__":
    unittest.main()
