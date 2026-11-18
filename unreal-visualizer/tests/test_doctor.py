import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from doctor import check_udp_bind, inspect

class DoctorTests(unittest.TestCase):
    def test_invalid_port(self):
        self.assertEqual(check_udp_bind(70000).state, "FAIL")
        self.assertEqual(check_udp_bind(0).state, "FAIL")
    def test_preflight_never_claims_electrical_pass(self):
        results = {r.name: r.state for r in inspect()}
        self.assertEqual(results["sensor electrical compatibility"], "MANUAL")
        self.assertEqual(results["motor isolation"], "MANUAL")
        self.assertEqual(results["pose observability"], "INFO")
    def test_preflight_has_unreal_source(self):
        results = {r.name: r.state for r in inspect()}
        self.assertEqual(results["Unreal source"], "PASS")

if __name__ == "__main__":
    unittest.main()
