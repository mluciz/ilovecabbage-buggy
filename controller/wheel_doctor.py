"""Wheel Doctor: offline pin-source audit and evidence-based wheel fault triage.

No motor command is emitted from this module. Positive pins and reported PWM are
*software expectations*, not measurements of physical wiring or rotation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
EXPECTED_PINS = {
    "STBY": 4, "PWMA": 5, "PWMB": 6, "AIN1": 7,
    "AIN2": 8, "BIN1": 9, "BIN2": 10,
}
BT_RX, BT_TX = 2, 3
STEPS = (
    ("left_forward", "LEFT FORWARD", 150, 0),
    ("left_reverse", "LEFT REVERSE", -150, 0),
    ("right_forward", "RIGHT FORWARD", 0, 150),
    ("right_reverse", "RIGHT REVERSE", 0, -150),
    ("both_forward", "BOTH FORWARD", 150, 150),
    ("both_reverse", "BOTH REVERSE", -150, -150),
)
RESULTS = {
    "NOT TESTED": "No observation recorded",
    "PASS": "Correct wheel(s) rotated; other wheel stationary",
    "NO MOVEMENT": "Expected wheel did not rotate",
    "WRONG DIRECTION": "A wheel moved opposite to command",
    "OTHER WHEEL MOVED": "Unexpected channel responded",
    "FAILED TO BRAKE": "Wheel kept moving after stop",
}


@dataclass(frozen=True)
class PinIssue:
    kind: str
    detail: str


def extract_pins(source: str) -> dict[str, int]:
    """Handles declarations both one-per-line and const byte A=4, B=5."""
    pins = {}
    for block in re.findall(r"\bconst\s+byte\s+([^;]+);", source):
        for name, value in re.findall(r"\b([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\b", block):
            if name in EXPECTED_PINS:
                pins[name] = int(value)
    return pins


def audit_sources(base: Path = ROOT) -> tuple[bool, list[str]]:
    """Read only local firmware sources. Cannot inspect a plugged-in circuit."""
    main = base / "arduino" / "BuggyController" / "BuggyController.ino"
    lab = base / "arduino" / "MotorTest" / "MotorTest.ino"
    lines = ["SOURCE PIN AUDIT  /  Arduino Uno + TB6612FNG + HM-10",
             "Source declarations only: NOT a continuity, voltage or rotation test.",
             ""]
    ok = True
    for label, filename in (("Controller firmware", main), ("Standalone MotorTest", lab)):
        try:
            content = filename.read_text(encoding="utf-8")
        except OSError as exc:
            ok = False
            lines.append(f"FAIL {label}: cannot read {filename.name}: {exc}")
            continue
        got = extract_pins(content)
        wrong = [f"{name} expected D{number}, got {('D'+str(got[name])) if name in got else 'MISSING'}"
                 for name, number in EXPECTED_PINS.items() if got.get(name) != number]
        if len(set(got.values())) != len(got):
            wrong.append("Two motor-control signals share a pin")
        if any(got.get(pwm) not in (5, 6) for pwm in ("PWMA", "PWMB")):
            wrong.append("PWM pins must be Arduino Uno PWM-capable D5/D6 in this design")
        if label == "Controller firmware":
            match = re.search(r"SoftwareSerial\s+BT\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", content)
            if not match or (int(match.group(1)), int(match.group(2))) != (BT_RX, BT_TX):
                wrong.append("Bluetooth RX/TX expected SoftwareSerial BT(2, 3)")
            for polarity in ("LEFT_MOTOR_POLARITY", "RIGHT_MOTOR_POLARITY"):
                if not re.search(rf"\b{polarity}\s*=\s*-?1\s*;", content):
                    wrong.append(f"{polarity} must explicitly be +1 or -1")
        if wrong:
            ok = False
            lines.append("FAIL " + label + ":")
            lines.extend("  - " + item for item in wrong)
        else:
            lines.append("PASS " + label + ": all seven motor-control pins match")
    # The Windows app has NO physical GPIO pins. Verify its abstract left/right
    # command order against the UART encoder and firmware channel mapping.
    try:
        bridge = (base / "ble_bridge.py").read_text(encoding="utf-8")
        app = (base / "app.py").read_text(encoding="utf-8")
        firmware = main.read_text(encoding="utf-8")
        checks = (
            ("BLE sends left PWM then right PWM", "f'M,{left},{right}\\n'" in bridge),
            ("GUI passes left/right to bridge without swapping", "self.bridge.set_motor(left, right)" in app),
            ("Firmware decodes leftText then rightText", bool(re.search(
                r"int left = atoi\(leftText\);\s*int right = atoi\(rightText\);", firmware))),
            ("Firmware maps left channel to PWMA and right channel to PWMB",
             "analogWrite(PWMA, l == 0 ? 255 : abs(l))" in firmware and
             "analogWrite(PWMB, r == 0 ? 255 : abs(r))" in firmware),
        )
        for label, passed in checks:
            lines.append(("PASS" if passed else "FAIL") + " protocol: " + label)
            if not passed:
                ok = False
    except OSError as exc:
        ok = False
        lines.append(f"FAIL unable to audit desktop-to-firmware protocol: {exc}")

    lines += [
        "",
        "REFERENCE (verify against actual wires with MOTOR BATTERY OFF):",
        "D4 -> STBY; D5 -> PWMA; D6 -> PWMB",
        "D7 -> AIN1; D8 -> AIN2; D9 -> BIN1; D10 -> BIN2",
        "Uno D2 RX <- HM-10 TXD; Uno D3 TX -> HM-10 RXD via logic divider",
        "TB6612 VCC -> Uno 5V; VM -> SWITCHED motor battery positive;",
        "Uno GND / driver GND / battery negative -> common GND",
        "AO1/AO2 -> left motor; BO1/BO2 -> right motor",
        "Use hardware power cutoff and ~10k STBY pulldown during reset.",
        "Do NOT connect the motor battery to the Uno 5V pin.",
        "The exact voltage needs of the HM-10 depend on the breakout board.",
        "",
        "PASS means code-to-code consistency, NOT verified physical wiring.",
    ]
    return ok, lines


def diagnose(observations: dict[str, str], *, connected=False, firmware_confirmed=False,
             rx_count=0, last_telemetry=None) -> str:
    """Explain competing causes without inferring sensors the buggy lacks."""
    problems = []
    for step, title, _, _ in STEPS:
        outcome = observations.get(step, "NOT TESTED")
        if outcome not in RESULTS:
            raise ValueError(f"Unrecognized observation for {title}: {outcome}")
        if outcome != "NOT TESTED":
            problems.append((step, title, outcome))

    out = ["BUGGY / WHEEL DOCTOR FIELD REPORT", "",
           f"BLE link: {'connected' if connected else 'disconnected / unverified'}",
           f"Firmware v1.6.5+ verified: {'yes' if firmware_confirmed else 'no'}",
           f"Arduino telemetry frames observed: {rx_count}",
           f"Last Arduino telemetry: {last_telemetry or 'none'}",
           "Remember: PWM, GATT writes and telemetry are NOT wheel-speed measurements.",
           "", "OBSERVATIONS:"]
    for step, title, _, _ in STEPS:
        out.append(f"  {title:<15} {observations.get(step, 'NOT TESTED')}")
    out += ["", "SUGGESTED NEXT CHECKS (in order):"]
    def advice(text):
        if text not in recommendations:
            recommendations.append(text)
    recommendations = []
    statuses = {s: observations.get(s, "NOT TESTED") for s, _, _, _ in STEPS}
    unsafe = any(value == "FAILED TO BRAKE" for value in statuses.values())
    if unsafe:
        advice("STOP: cut motor-battery power immediately. Do not repeat powered testing. Inspect TB6612FNG outputs, stuck driver, shorted wiring and accessible cutoff before further use.")
    elif not problems:
        advice("Start with SOURCE PIN AUDIT; then verify wires with motor power OFF. Raise both wheels, keep the battery switch accessible, and test one direction at a time.")
    if not connected:
        advice("The app has no verified BLE connection. Check Windows Bluetooth, HM-10 power/advertising, selected UART characteristic (often FFE1), and USB firmware upload.")
    if connected and not firmware_confirmed:
        advice("BLE connection alone does not prove the correct Arduino sketch. Upload this candidate firmware and confirm V,165 reply before app-driven pulses; alternatively use MotorTest.ino via USB.")
    if connected and rx_count == 0:
        advice("No Arduino telemetry observed: check notify capability, HM-10 TXD->Uno D2, Uno D3->HM-10 RXD through divider, common ground and 9600 baud. No notifications alone do not prove a failed drive path.")
    for side in ("left", "right"):
        side_results = [statuses[side + "_forward"], statuses[side + "_reverse"]]
        if side_results == ["NO MOVEMENT", "NO MOVEMENT"]:
            channel = "A / AO1-AO2 / PWMA / AIN1-AIN2" if side == "left" else "B / BO1-BO2 / PWMB / BIN1-BIN2"
            advice(f"{side.upper()} is dead both ways: with power OFF inspect motor terminal wires, TB6612 channel {channel}, motor-battery VM, common ground, STBY HIGH, and whether the motor itself is seized. A controller fault is possible.")
        elif "NO MOVEMENT" in side_results:
            direction = "forward" if side_results[0] == "NO MOVEMENT" else "reverse"
            advice(f"{side.upper()} only fails {direction}: inspect its two direction-input wires and output channel; check mechanical drag and supply sag. A correct received PWM is not electrical proof.")
        if "WRONG DIRECTION" in side_results:
            advice(f"{side.upper()} spins in the opposite direction: inspect physical motor mounting / AO or BO polarity. Only after confirming correct wiring, adjust {side.upper()}_MOTOR_POLARITY (+1/-1) in BuggyController.ino, then reflash with motor power OFF.")
        if "OTHER WHEEL MOVED" in side_results:
            advice(f"{side.upper()} command moved the other wheel: channel A/B motor plugs or mapping may be swapped; trace outputs to actual wheels with power OFF.")
    if all(statuses[s] == "NO MOVEMENT" for s in ("left_forward","left_reverse","right_forward","right_reverse")):
        advice("Neither channel moves: prioritize switched motor-battery VM voltage under load, battery polarity, STBY, TB6612 VCC and shared GND. Arduino USB power alone cannot drive motors.")
    if all(statuses[s] == "PASS" for s in ("left_forward", "left_reverse", "right_forward", "right_reverse")):
        advice("Both channels worked independently. If WASD still fails, investigate keyboard activation, GATT writes, Arduino RX command count and the emergency-stop/re-arm state instead of rewiring motors.")
    if not recommendations:
        advice("Record the exact failing direction and run the standalone MotorTest.ino with wheels raised. Its six stages bypass Bluetooth and the Windows GUI to isolate the driver and physical motors.")
    out += [f"{i}. {item}" for i, item in enumerate(recommendations, 1)]
    out += ["", "Physical safety: no wheel encoders, current monitor or VM-voltage sensor are installed.",
            "Never test with wheels touching a surface until all channels and braking pass."]
    return "\n".join(out) + "\n"
