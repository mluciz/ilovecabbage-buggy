"""Regression tests for the real v1.6.4 GUI/bridge and safety firmware pairing.

No Bluetooth hardware or Tk display is needed for these pure/transport tests.
"""
import asyncio
import queue
import threading
import time

from motor_control import manual_wheels, parse_telemetry
from ble_bridge import BLEBridge


def test_conflicting_forward_reverse_never_pivot():
    for gear in (0, 80, 150, 220, 255):
        for extra in (set(), {'A'}, {'D'}, {'A', 'D'}):
            assert manual_wheels({'W', 'S'} | extra, gear, 100) == (0, 0)


def test_forward_and_turn_signs():
    assert manual_wheels({'W'}, 175, 50) == (175, 175)
    assert manual_wheels({'S'}, 175, 50) == (-175, -175)
    assert manual_wheels({'A'}, 175, 100) == (-175, 175)
    assert manual_wheels({'D'}, 175, 100) == (175, -175)
    l, r = manual_wheels({'W', 'A'}, 175, 50)
    assert 0 <= l < r == 175
    l, r = manual_wheels({'W', 'D'}, 175, 50)
    assert 0 <= r < l == 175


def test_motor_telemetry_emergency_state():
    reading = parse_telemetry('T,0,0,E,3,125')
    assert reading is not None
    assert reading.state == 'LATCHED EMERGENCY STOP'
    assert reading.left_pwm == 0 and reading.right_pwm == 0


def test_ble_emergency_stop_needs_explicit_rearm():
    class FakeClient:
        is_connected = True
        def __init__(self):
            self.sent = []
        async def write_gatt_char(self, _char, data, response=False):
            self.sent.append(bytes(data))

    async def run():
        bridge = object.__new__(BLEBridge)
        bridge._write_lock = asyncio.Lock()
        bridge._lock = threading.Lock()
        bridge.events = queue.Queue()
        bridge.client = FakeClient()
        bridge.char = 'FFE1'
        bridge.write_response = False
        bridge._motor = (0, 0)
        bridge._brake = True
        bridge._emergency_latched = True
        bridge._updated = time.monotonic()

        bridge.set_motor(150, -150)
        assert bridge._motor == (0, 0)  # Latch blocks queued wheel intent.

        await bridge._send_emergency_latch()
        assert bridge.client.sent == [b'K\n', b'X\n']
        await bridge._release_emergency()
        assert bridge.client.sent[-2:] == [b'U\n', b'M,0,0\n']
        assert not bridge._emergency_latched
        bridge.set_motor(150, -150)
        assert bridge._motor == (150, -150)
        await bridge._send()
        assert bridge.client.sent[-1] == b'M,150,-150\n'

    asyncio.run(run())
