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


def test_repeated_emergency_clicks_coalesce_and_preserve_watchdog_margin():
    import ble_bridge

    assert ble_bridge.DRIVE_STREAM_INTERVAL_S < 0.30
    assert ble_bridge.CONGESTED_DRIVE_INTERVAL_S < 0.30
    assert ble_bridge.BRAKE_STREAM_INTERVAL_S < 1.20
    assert ble_bridge.GATT_WRITE_TIMEOUT_S < 1.20

    class FakeClient:
        is_connected = True

    bridge = object.__new__(BLEBridge)
    bridge.client = FakeClient()
    bridge.char = 'FFE1'
    bridge._lock = threading.Lock()
    bridge._motor = (150, 150)
    bridge._brake = False
    bridge._emergency_latched = False
    bridge._safety_epoch = 0
    bridge._emergency_send_pending = False
    bridge._updated = time.monotonic()
    pending = []

    def schedule(coro):
        pending.append(coro)

    bridge._schedule = schedule
    bridge.latch_emergency()
    bridge.latch_emergency()
    assert bridge._brake is True and bridge._motor == (0, 0)
    assert bridge._emergency_latched is True
    # set_brake queues one urgent brake; repeated emergency requests add
    # only one emergency sequence, not one per key repeat/focus event.
    assert len(pending) == 2
    assert bridge._emergency_send_pending is True
    for coro in pending:
        coro.close()


def test_pivot_uses_full_selected_gear_to_overcome_static_friction():
    """Pure A/D turns must not secretly derate power below W/S gear PWM."""
    for pwm in (0, 80, 110, 150, 200, 240, 255):
        for sensitivity in (0, 25, 50, 75, 100):
            assert manual_wheels({'A'}, pwm, sensitivity) == (-pwm, pwm)
            assert manual_wheels({'D'}, pwm, sensitivity) == (pwm, -pwm)
            assert manual_wheels({'W'}, pwm, sensitivity) == (pwm, pwm)
            assert manual_wheels({'S'}, pwm, sensitivity) == (-pwm, -pwm)


def test_combined_steering_may_slow_inside_wheel_by_design():
    # W+A / W+D are curves (inside wheel slower) rather than counter-rotating
    # pivots. A stationary inside wheel at high sensitivity is not necessarily
    # failed hardware.
    for sensitivity in (0, 50, 100):
        left, right = manual_wheels({'W', 'A'}, 200, sensitivity)
        assert 0 <= left < right == 200
        left, right = manual_wheels({'W', 'D'}, 200, sensitivity)
        assert 0 <= right < left == 200
