import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from route_planner import Planner, advance_pose, sample_path


class RouteTests(unittest.TestCase):
    def test_circle_returns_close_to_origin(self):
        p = Planner(full_speed_cm_s=22, wheelbase_cm=13, gear=4)
        segs = p.build('circle', radius=25, laps=1)
        pose = (0, 0, 0)
        for s in segs:
            pose = advance_pose(pose, s, s.duration, p.max_speed, p.wheelbase)
        # The tiny discrepancy is from mapping wheel ratio to integer PWM.
        self.assertLess(math.hypot(pose[0], pose[1]), 1.0)
        self.assertAlmostEqual(abs(pose[2]), 2 * math.pi, delta=.1)

    def test_oval_closes_near_origin(self):
        p = Planner(22, 13, 4)
        segments = p.build('oval', radius=20, length=60, laps=1)
        self.assertEqual(len(segments), 4)
        pose = (0, 0, 0)
        for s in segments:
            pose = advance_pose(pose, s, s.duration, p.max_speed, p.wheelbase)
        self.assertLess(math.hypot(pose[0], pose[1]), 2.0)

    def test_zigzag_number_of_steps(self):
        p = Planner()
        segments = p.build('zigzag', length=40, legs=5, angle=45)
        self.assertEqual(len(segments), 9)
        self.assertEqual(len(sample_path(segments, p.max_speed, p.wheelbase)) > 9, True)

    def test_custom_parse(self):
        p = Planner()
        segments = p.build('custom', custom='F 50\nL 90\nARC R 25 180\nB 20')
        self.assertEqual(len(segments), 4)
        self.assertLess(segments[-1].left, 0)

    def test_custom_invalid(self):
        p = Planner()
        with self.assertRaises(ValueError):
            p.build('custom', custom='FLY 99')

    def test_pivot_left(self):
        p = Planner(22, 13, 4)
        segment = p.build('custom', custom='L 90')[0]
        final = advance_pose((0, 0, 0), segment, segment.duration, 22, 13)
        self.assertAlmostEqual(final[2], math.pi/2, places=4)

    def test_safety_limits(self):
        p = Planner()
        with self.assertRaises(ValueError):
            p.build('circle', radius=2000)


if __name__ == '__main__':
    unittest.main()
