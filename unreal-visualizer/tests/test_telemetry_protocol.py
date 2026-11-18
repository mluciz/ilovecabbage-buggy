"""stdlib test suite: python -m unittest discover -s tests -v"""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from telemetry_protocol import (TelemetryError, validate_packet, encode_payload, decode_payload)
from demo_sender import demo_packet, intersect_box

def sample():
    return {"schema": 2, "source": "unit-test",
            "sensors": [{"id": n, "valid": True, "distance_mm": 250.} for n in ("front", "left", "right")],
            "pose": {"x_m": 0, "y_m": 0, "yaw_deg": 0},
            "imu": {"gyro_x_dps": 0, "gyro_y_dps": 0, "gyro_z_dps": 0,
                    "accel_x_g": 0, "accel_y_g": 0, "accel_z_g": 1, "dt_s": .05}}

class ThreeSensorProtocolTests(unittest.TestCase):
    def test_exact_three_distinct(self):
        self.assertEqual(len(validate_packet(sample())["sensors"]), 3)
        bad = sample()
        bad["sensors"][2]["id"] = "front"
        with self.assertRaises(TelemetryError): validate_packet(bad)
    def test_reject_missing_sensor(self):
        p = sample()
        p["sensors"].pop()
        with self.assertRaises(TelemetryError): validate_packet(p)
    def test_reject_unknown_sensor(self):
        p = sample()
        p["sensors"][0]["id"] = "rear"
        with self.assertRaises(TelemetryError): validate_packet(p)
    def test_reject_ambiguous_valid_flag(self):
        p = sample()
        p["sensors"][0]["valid"] = "true"
        with self.assertRaises(TelemetryError): validate_packet(p)
    def test_reject_nan_inf_and_range(self):
        for distance in (math.nan, math.inf, -1, 2010, "120"):
            p = sample()
            p["sensors"][0]["distance_mm"] = distance
            with self.subTest(distance=distance), self.assertRaises(TelemetryError):
                validate_packet(p)
    def test_invalid_sensor_requires_no_range(self):
        p = sample()
        p["sensors"][1] = {"id": "left", "valid": False}
        out = validate_packet(p)
        self.assertEqual(out["sensors"][1], {"id": "left", "valid": False})
    def test_reject_bad_imu(self):
        p = sample()
        p["imu"]["gyro_x_dps"] = float("inf")
        with self.assertRaises(TelemetryError): validate_packet(p)
    def test_reject_bad_pose(self):
        p = sample()
        p["pose"]["x_m"] = float("nan")
        with self.assertRaises(TelemetryError): validate_packet(p)
    def test_reject_oversize(self):
        with self.assertRaises(TelemetryError):
            decode_payload(b" " * 4097)
    def test_round_trip(self):
        p = sample()
        self.assertEqual(decode_payload(encode_payload(p))["sensors"], p["sensors"])
    def test_demo_all_three_sensor_ids(self):
        for t in (0, 1, 5, 10, 30, 60):
            for scenario in ("arena", "sensor-dropout", "turning"):
                p = demo_packet(t, scenario)
                self.assertEqual(tuple(s["id"] for s in p["sensors"]), ("front", "left", "right"))
                self.assertEqual(len(decode_payload(encode_payload(p))["sensors"]), 3)
    def test_ray_intersection(self):
        self.assertEqual(intersect_box(0, 0, 1, 0, (100, 0, 20, 20)), 80)
        self.assertIsNone(intersect_box(0, 0, 0, 1, (100, 0, 20, 20)))
        self.assertIsNone(intersect_box(0, 0, 1, 0, (500, 0, 20, 20)))

if __name__ == "__main__":
    unittest.main()
