from route_planner import GEARS
from motor_control import manual_wheels
from pathlib import Path

def test_high_output_gears_are_distinct_and_within_arduino_pwm_limits():
    assert GEARS == {1: 215, 2: 230, 3: 243, 4: 255}
    assert len(set(GEARS.values())) == 4
    assert max(GEARS.values()) == 255
    for gear in GEARS.values():
        assert manual_wheels({"S"}, gear, 50) == (-gear, -gear)
        assert manual_wheels({"W"}, gear, 50) == (gear, gear)

def test_firmware_starts_with_brake_and_has_both_right_direction_pins():
    firmware = (Path(__file__).resolve().parents[1] / "arduino/BuggyController/BuggyController.ino").read_text()
    setup = firmware.split("void setup() {",1)[1].split("void loop()",1)[0]
    assert "commandWheels(0, 0);" not in setup
    assert "digitalWrite(BIN1, HIGH);" in setup and "digitalWrite(BIN2, HIGH);" in setup
    assert "analogWrite(PWMB, 255);" in setup
    assert "digitalWrite(STBY, HIGH);" in setup

def test_link_brakes_before_streaming():
    bridge = (Path(__file__).resolve().parents[1] / "ble_bridge.py").read_text()
    connect = bridge.split("async def _connect(",1)[1].split("def _notification",1)[0]
    assert connect.index("await self._send(brake=True)") < connect.index("self.stream_task = asyncio.create_task(self._stream())")
