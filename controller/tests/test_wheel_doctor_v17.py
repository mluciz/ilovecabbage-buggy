"""Offline regression: never requires a real buggy, Bluetooth adapter or wheel sensor."""
import asyncio
import queue
import threading
import time

from ble_bridge import BLEBridge
from wheel_doctor import EXPECTED_PINS, STEPS, audit_sources, diagnose, extract_pins


def test_pin_declarations_match_between_both_actual_arduino_sketches():
    ok, lines = audit_sources()
    assert ok, "\n".join(lines)
    assert len(EXPECTED_PINS) == 7
    assert "physical wiring" in "\n".join(lines).lower()


def test_pin_audit_rejects_swapped_direction_pin(tmp_path):
    firmware = tmp_path / "arduino" / "BuggyController"
    lab = tmp_path / "arduino" / "MotorTest"
    firmware.mkdir(parents=True)
    lab.mkdir(parents=True)
    sample = "\n".join("const byte {} = {};".format(n, p)
                       for n, p in EXPECTED_PINS.items())
    (firmware / "BuggyController.ino").write_text(
        sample.replace("AIN1 = 7", "AIN1 = 9") +
        "\nSoftwareSerial BT(2, 3);\nconst int LEFT_MOTOR_POLARITY=1;\n"
        "const int RIGHT_MOTOR_POLARITY=-1;\n", encoding="utf-8")
    (lab / "MotorTest.ino").write_text(sample, encoding="utf-8")
    ok, lines = audit_sources(tmp_path)
    assert not ok
    assert any("AIN1 expected D7, got D9" in line for line in lines)
    assert any("share a pin" in line for line in lines)


def test_extract_pins_handles_grouped_standalone_motor_lab_declarations():
    text = "const byte STBY=4, PWMA=5, PWMB=6, AIN1=7, AIN2=8, BIN1=9, BIN2=10;"
    assert extract_pins(text) == EXPECTED_PINS


def test_wheel_diagnosis_is_manual_evidence_not_fake_sensors():
    report = diagnose({"right_forward": "NO MOVEMENT", "right_reverse": "NO MOVEMENT"},
                      connected=True, firmware_confirmed=True, rx_count=42,
                      last_telemetry="L 0, R 0, ACTIVE BRAKE")
    assert "B / BO1-BO2 / PWMB / BIN1-BIN2" in report
    assert "wheel-speed measurements" in report
    assert "RX" not in report or "Arduino telemetry" in report


def test_wrong_direction_and_swapped_channels_are_not_conflated():
    report = diagnose({"left_reverse": "WRONG DIRECTION",
                       "right_forward": "OTHER WHEEL MOVED"})
    assert "LEFT_MOTOR_POLARITY" in report
    assert "mapping may be swapped" in report


def test_failed_to_brake_forces_stop_first():
    report = diagnose({"right_reverse": "FAILED TO BRAKE"})
    assert "STOP: cut motor-battery power immediately." in report
    assert len(STEPS) == 6


class FakeClient:
    is_connected = True

    def __init__(self, on_send=None):
        self.sent = []
        self.on_send = on_send

    async def write_gatt_char(self, _char, data, response=False):
        self.sent.append(bytes(data))
        if self.on_send:
            self.on_send(bytes(data))


def mock_bridge(version=True):
    bridge = object.__new__(BLEBridge)
    bridge._write_lock = asyncio.Lock()
    bridge._lock = threading.Lock()
    bridge.events = queue.Queue()
    bridge.client = FakeClient()
    bridge.char = "FFE1"
    bridge.write_response = False
    bridge._motor = (0, 0)
    bridge._brake = True
    bridge._emergency_latched = True
    bridge._safety_epoch = 17
    bridge._version_confirmed = version
    bridge._pulse_active = True
    bridge._updated = time.monotonic()
    return bridge


def test_single_channel_pulse_requires_v165_and_ends_with_emergency_latch():
    async def run():
        bridge = mock_bridge(version=True)
        await bridge._pulse_wheel(0, -150, 0.12, 17)
        sent = bridge.client.sent
        assert sent[:2] == [b"U\n", b"M,0,0\n"]
        assert b"M,0,-150\n" in sent
        assert sent[-2:] == [b"K\n", b"X\n"]
        assert bridge._emergency_latched is True
        assert bridge._brake is True
        assert bridge._motor == (0, 0)
        assert bridge._pulse_active is False
        assert "Test command window ended" in bridge.events.get_nowait()[1]
    asyncio.run(run())


def test_pulse_rejects_older_firmware_without_driving():
    async def run():
        bridge = mock_bridge(version=False)
        await bridge._pulse_wheel(150, 0, 0.12, 17)
        assert not any(msg.startswith(b"M,150") for msg in bridge.client.sent)
        assert bridge.client.sent[-2:] == [b"K\n", b"X\n"]
        assert "TRANSPORT ERROR" in bridge.events.get_nowait()[1]
    asyncio.run(run())


def test_newer_emergency_cancels_diagnostic_pulse():
    async def run():
        bridge = mock_bridge(version=True)

        def stop_after_one_frame(data):
            if data == b"M,150,0\n":
                with bridge._lock:
                    bridge._safety_epoch += 1

        bridge.client = FakeClient(on_send=stop_after_one_frame)
        await bridge._pulse_wheel(150, 0, 0.4, 17)
        assert bridge.client.sent.count(b"M,150,0\n") == 1
        assert bridge.client.sent[-2:] == [b"K\n", b"X\n"]
        assert "cancelled by emergency stop" in bridge.events.get_nowait()[1]
    asyncio.run(run())


def test_fragmented_version_response_requires_complete_line():
    bridge = mock_bridge(version=False)
    bridge._rx_partial = bytearray()
    bridge._notification(None, b"V,1")
    assert bridge._version_confirmed is False
    bridge._notification(None, b"65\n")
    assert bridge._version_confirmed is True
    assert bridge.events.get_nowait() == ("firmware_version", 165)
