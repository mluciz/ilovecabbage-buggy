"""v1.6.4: telemetry-first UART issue, BLE stall safety, optional precision."""
import asyncio
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

import pytest

from app import BuggyApp
from ble_bridge import BLEBridge, GATT_WRITE_TIMEOUT_S
from link_stress_lab import simulate_link, offline_link_stress_check
from motor_control import parse_telemetry


def test_optional_arduino_receive_counter_backwards_compatible():
    old = parse_telemetry('T,110,-120,D,11')
    assert old.left_pwm == 110 and old.right_pwm == -120
    assert old.accepted_commands is None
    new = parse_telemetry('T,0,0,B,12,4567')
    assert new.accepted_commands == 4567
    assert parse_telemetry('T,0,0,B,12,4294967296') is None
    assert parse_telemetry('T,0,0,B,12,wat') is None


def test_virtual_link_model_contains_expected_watchdog_fail_safe():
    ok, detail = offline_link_stress_check()
    assert ok
    assert 'Synthetic proof' in detail
    normal = simulate_link('normal', drop_every=12)
    broken = simulate_link('outage', blackout=(8, 10), drop_every=12)
    assert normal.watchdog_trips == 0
    assert broken.watchdog_trips == 1
    assert broken.stayed_locked_after_outage


def test_arduino_suppresses_all_uart_transmission_during_motion():
    sketch = (Path(__file__).resolve().parents[1] / 'arduino/BuggyController/BuggyController.ino').read_text()
    assert 'TELEMETRY_WHILE_MOVING = false' in sketch
    assert '(currentLeft == 0 && currentRight == 0 && !reversalPending)' in sketch
    assert 'watchdogLockout = true' in sketch


def test_bridge_write_timeout_reports_hang():
    class Slow:
        is_connected = True
        async def write_gatt_char(self, *_args, **_kwargs):
            await asyncio.sleep(4)

    async def run():
        bridge = object.__new__(BLEBridge)
        bridge.client = Slow()
        bridge._write_lock = asyncio.Lock()
        bridge._lock = threading.Lock()
        bridge._motor = (220, 220)
        bridge._brake = False
        bridge._updated = time.monotonic()
        bridge.char = 'FFE1'
        bridge.write_response = False
        bridge.events = queue.Queue()
        started = time.monotonic()
        with pytest.raises(RuntimeError, match='GATT write stalled'):
            await bridge._send()
        assert time.monotonic() - started < 2.0
    asyncio.run(run())


def test_precision_mode_changes_manual_pwm_and_latches_brake_when_switched():
    root = tk.Tk()
    app = BuggyApp(root)
    try:
        app.demo_var.set(True)
        app.toggle_connection()
        root.update()
        app._press('W')
        assert app._manual_wheels() == (255, 255)  # default BOOST gear 2
        app.precision_var.set(True)
        app._precision_changed()
        assert app.brake_latched and not app.pressed
        app._release('W')  # true release is required after mode-change brake
        app._press('W')
        assert app._manual_wheels() == (150, 150)
        app._release('W')
        assert app.brake_latched
        app.set_gear(1)
        assert app._manual_pwm() == 110
        app.set_gear(4)
        assert app._manual_pwm() == 240
    finally:
        app._shutdown()
        root.destroy()


def test_accepted_command_counter_visible_in_gui():
    root = tk.Tk()
    app = BuggyApp(root)
    try:
        app.demo_var.set(True)
        app.toggle_connection()
        app.bridge.events.put(('telemetry', (parse_telemetry('T,0,0,B,1,42'), time.monotonic())))
        app._events()
        assert 'RX CMD 42' in app.telemetry_state_var.get()
        assert any('rx_commands=42' in str(row) for row in app.flight.snapshot())
    finally:
        app._shutdown()
        root.destroy()


def test_offline_link_stress_never_requires_real_ble():
    root = tk.Tk()
    app = BuggyApp(root)
    try:
        app.demo_var.set(True)
        app.toggle_connection()
        import unittest.mock as mock
        with mock.patch('app.messagebox.showinfo') as info:
            app.run_link_stress_check()
            assert info.called
            assert 'Synthetic proof' in info.call_args.args[-1]
    finally:
        app._shutdown()
        root.destroy()


def test_escape_is_global_brake_even_during_text_entry():
    root = tk.Tk()
    app = BuggyApp(root)
    try:
        app.demo_var.set(True)
        app.toggle_connection()
        entry = tk.Entry(root)
        entry.pack()
        app._press('W')
        assert app.pressed == {'W'}
        event = type('E', (), {'keysym': 'Escape', 'char': '', 'widget': entry})()
        result = app._key_down(event)
        assert result == 'break'
        assert not app.pressed and app.brake_latched
    finally:
        app._shutdown()
        root.destroy()


def test_space_in_text_field_does_not_prevent_typing():
    root = tk.Tk()
    app = BuggyApp(root)
    try:
        entry = tk.Entry(root)
        entry.pack()
        event = type('E', (), {'keysym': 'space', 'char': ' ', 'widget': entry})()
        assert app._key_down(event) is None
    finally:
        app._shutdown()
        root.destroy()
