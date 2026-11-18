from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def test_watchdog_is_still_enabled():
    fw = (ROOT/'arduino/BuggyController/BuggyController.ino').read_text()
    assert 'WATCHDOG_MS = 1200' in fw
    assert "activeBrake('W')" in fw
    assert 'TELEMETRY_MS = 1000' in fw
    assert 'if (left == 0 && right == 0)' in fw

def test_transport_is_less_aggressive():
    bridge = (ROOT/'ble_bridge.py').read_text()
    # v1.6.5 safety deliberately slowed the period to 160ms (< watchdog margin).
    assert 'DRIVE_STREAM_INTERVAL_S = 0.16' in bridge
    assert 'if age > 0.90:' in bridge

def test_keyboard_requires_confirmed_release():
    app = (ROOT/'app.py').read_text()
    assert 'if misses >= 3:' in app
    assert 'self._physical_key_misses.clear()' in app
