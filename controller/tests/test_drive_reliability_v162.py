"""Regression coverage for transport races, key sources and Arduino logic."""
from __future__ import annotations
import asyncio
import queue
import shutil
import pytest
import subprocess
import threading
import time
from pathlib import Path

from ble_bridge import BLEBridge
from motor_control import manual_wheels
from route_planner import GEARS

ROOT = Path(__file__).resolve().parents[1]


def test_both_wheels_have_same_forward_and_reverse_commands():
    for gear in GEARS.values():
        assert manual_wheels({'W'}, gear, 50) == (gear, gear)
        assert manual_wheels({'S'}, gear, 50) == (-gear, -gear)
        assert manual_wheels(set(), gear, 50) == (0, 0)


class FakeClient:
    def __init__(self):
        self.is_connected = True
        self.writes = []
    async def write_gatt_char(self, _char, data, response=False):
        self.writes.append(bytes(data))


def make_bridge():
    # Do not create a thread or access physical BLE hardware during these tests.
    bridge = object.__new__(BLEBridge)
    bridge._write_lock = asyncio.Lock()
    bridge._lock = threading.Lock()
    bridge._brake = True
    bridge._motor = (0, 0)
    bridge._updated = time.monotonic()
    bridge.client = FakeClient()
    bridge.char = 'test'
    bridge.write_response = False
    bridge.events = queue.Queue()
    bridge._tx_count = 0
    bridge._last_tx_report = time.monotonic()
    return bridge


def test_transport_uses_latest_state_not_queued_snapshots():
    async def scenario():
        b = make_bridge()
        b._motor = (120, -190)
        b._brake = False
        await b._send(left=0, right=0, brake=False)
        assert b.client.writes == [b'M,120,-190\n']
        # An old urgent brake scheduled before a new key press must be ignored.
        await b._send(brake=True)
        assert b.client.writes == [b'M,120,-190\n']
        b._brake = True
        await b._send(left=255, right=255, brake=False)
        assert b.client.writes[-1] == b'K\n'
        b._brake = False
        b._updated = time.monotonic() - 1.5
        await b._send()
        assert b.client.writes[-1] == b'K\n'
    asyncio.run(scenario())


def test_held_drive_streams_then_brakes_without_old_commands():
    async def scenario():
        b = make_bridge()
        b._brake = False
        b._motor = (-220, -220)
        task = asyncio.create_task(b._stream())
        await asyncio.sleep(0.40)
        b._brake = True
        b._motor = (0, 0)
        await asyncio.sleep(0.27)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert len(b.client.writes) >= 4
        assert all(x == b'M,-220,-220\n' for x in b.client.writes[:3])
        assert b'K\n' in b.client.writes
        first_brake = b.client.writes.index(b'K\n')
        assert all(x == b'K\n' for x in b.client.writes[first_brake:])
    asyncio.run(scenario())


def test_arduino_motor_logic_compiles_and_simulates(tmp_path):
    """Compile exact production .ino against pin mocks, then test output signals."""
    if not shutil.which('g++'):
        pytest.skip('g++ unavailable: firmware host simulation is optional on Windows')
    executable = tmp_path / 'firmware_test'
    source = ROOT / 'tests/firmware_mock/firmware_harness.cpp'
    includes = ROOT / 'tests/firmware_mock'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', str(includes),
                    str(source), '-o', str(executable)], check=True, capture_output=True, text=True)
    completed = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    assert 'PASS' in completed.stdout
