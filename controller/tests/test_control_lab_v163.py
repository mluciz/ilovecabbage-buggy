"""v1.6.3: tests for physical key repeat, motor balance and offline evidence."""
import asyncio
import csv
import queue
import threading
import time
import tkinter as tk

from app import BuggyApp
from ble_bridge import BLEBridge
from flight_recorder import FlightRecorder, offline_control_check
from motor_control import balance_wheels


def test_balance_only_reduces_stronger_side_and_preserves_sign():
    assert balance_wheels(255, 255, 0) == (255, 255)
    assert balance_wheels(255, 255, 30) == (178, 255)
    assert balance_wheels(-220, -220, -30) == (-220, -154)
    assert balance_wheels(0, -220, 30) == (0, -220)
    assert balance_wheels(-220, 0, -30) == (-220, 0)
    assert balance_wheels(220, 220, 999) == (154, 220)


def test_offline_check_does_not_require_ble_hardware():
    ok, desc = offline_control_check()
    assert ok
    assert '42' in desc


def test_trace_is_bounded_and_can_export_csv(tmp_path):
    f = FlightRecorder(capacity=3)
    for i in range(8):
        f.record('BLE_TX', f'M,{i},{i}', 'test')
    assert f.count == 3
    assert [row[3] for row in f.snapshot()] == ['M,5,5', 'M,6,6', 'M,7,7']
    path = f.export_csv(tmp_path / 'motor_commands.csv')
    with path.open(encoding='utf-8-sig', newline='') as inp:
        lines = list(csv.DictReader(inp))
    assert len(lines) == 3
    assert lines[-1]['event'] == 'M,7,7'
    assert lines[0]['source'] == 'BLE_TX'


def fake_app():
    root = tk.Tk()
    app = BuggyApp(root)
    root.update()
    app.demo_var.set(True)
    app.toggle_connection()
    root.update()
    return root, app


def evt(app, name):
    return type('Event', (), {'keysym': name, 'char': name, 'widget': app.drive_panel})()


def test_windows_repeat_not_releasing_physical_held_key():
    root, app = fake_app()
    try:
        app._physical_key_down = lambda key: True
        app._key_down(evt(app, 'w'))
        assert app.pressed == {'W'}
        app._key_up(evt(app, 'w'))
        time.sleep(0.08)
        root.update()
        assert app.pressed == {'W'}
        assert app._keyboard_pressed == {'W'}
        app._physical_key_down = lambda key: False
        app._key_up(evt(app, 'w'))
        time.sleep(0.08)
        root.update()
        assert not app.pressed
        assert app.brake_latched
        app._shutdown()
    finally:
        root.destroy()


def test_brake_latch_cannot_rearm_on_fake_release():
    root, app = fake_app()
    try:
        app._physical_key_down = lambda key: True
        app._key_down(evt(app, 'w'))
        app.emergency_stop()
        app._key_up(evt(app, 'w'))
        time.sleep(0.08)
        root.update()
        assert 'W' in app._blocked_drive_keys
        app._key_down(evt(app, 'w'))
        assert app.brake_latched
        app._physical_key_down = lambda key: False
        app._key_up(evt(app, 'w'))
        time.sleep(0.08)
        root.update()
        assert 'W' not in app._blocked_drive_keys
        app._key_down(evt(app, 'w'))
        assert not app.brake_latched
        app._shutdown()
    finally:
        root.destroy()


def test_ui_stall_causes_safety_brake():
    root, app = fake_app()
    try:
        app.demo = False  # simulate actual-link UI state, no hardware calls: monkeypatch
        app.bridge.set_brake = lambda: None
        app.bridge.set_motor = lambda *_: None
        app._press('W', source='api')
        assert app.pressed
        app._last_tick_at -= 2.0
        app._tick()
        assert app.brake_latched
        assert not app.pressed
        assert any(row[3] == 'GUI_STALL_BRAKE' for row in app.flight.snapshot())
        app._shutdown()
    finally:
        root.destroy()


def test_ble_write_event_contains_actual_packet_and_latency():
    class C:
        is_connected = True
        async def write_gatt_char(self, _char, data, response=False):
            self.data = data

    async def run():
        b = object.__new__(BLEBridge)
        b._write_lock = asyncio.Lock()
        b._lock = threading.Lock()
        b.events = queue.Queue()
        b.client = C()
        b.char = 'FFE1'
        b.write_response = False
        b._motor = (135, -172)
        b._brake = False
        b._updated = time.monotonic()
        await b._send()
        assert b.client.data == b'M,135,-172\n'
        kind, event = b.events.get_nowait()
        assert kind == 'tx_frame'
        assert event['frame'] == 'M,135,-172'
        assert 0 < time.monotonic() - event['sent_at'] < 0.5
        assert 0 <= event['intent_age_ms'] < 200
        assert event['latency_ms'] >= 0
        b._brake = True
        await b._send()
        assert b.client.data == b'K\n'
    asyncio.run(run())


def test_manual_balance_affects_manual_but_not_route():
    root, app = fake_app()
    try:
        app.balance_var.set(30)
        app._press('W')
        assert app._manual_wheels() == (178, 255)  # default gear 2
        app._release('W')
        assert app.brake_latched
        app.preview_route()
        assert app.route
        assert any(segment.left == 255 or segment.right == 255 for segment in app.route)
        app._shutdown()
    finally:
        root.destroy()


def test_motor_lab_requires_explicit_serial_arm():
    from pathlib import Path
    sketch = (Path(__file__).resolve().parents[1] / 'arduino/MotorTest/MotorTest.ino').read_text()
    setup = sketch.split('void setup() {')[1].split('void loop() {')[0]
    assert 'test(F(' not in setup
    assert 'brake();' in setup
    assert "c == 'T'" in sketch
    assert 'RIGHT REVERSE' in sketch


def test_motor_lab_compiles_and_runs_with_pin_mocks(tmp_path):
    import shutil
    import subprocess
    import pytest
    from pathlib import Path
    if not shutil.which('g++'):
        pytest.skip('C++ host compiler unavailable: optional motor lab simulation')
    root = Path(__file__).resolve().parents[1]
    harness = root / 'tests/firmware_mock/motor_lab_harness.cpp'
    executable = tmp_path / 'motor_lab'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', str(root/'tests/firmware_mock'),
                    str(harness), '-o', str(executable)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(executable)], capture_output=True, text=True, check=True)
    assert 'PASS' in result.stdout
