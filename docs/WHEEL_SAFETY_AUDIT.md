# Wheel and Bluetooth movement audit — 11 November 2026

Status: **candidate v1.6.5-safety, software changes proposed; hardware NOT verified**.

## What was actually reviewed

The current `main` GitHub repository now contains the **complete v1.6.4 Windows GUI and Python BLE transport**, Arduino controller, route planner, diagnostics, flight recorder, tests, and bundled downloads. This branch edits that actual original app; it does not replace its advanced interface or route features.

The original right wheel was reported to sometimes move on its own and to fail reversing/braking. A damaged motor driver, wiring, battery or a polarity reversal can produce this even if all computer tests pass. **Do not drive on a floor until the right channel has passed the bench tests.**

## Verified source-level defects / mitigations

| Source | Diagnosis | Change |
|---|---|---|
| Arduino firmware | BLE and USB input shared a partial packet buffer. Interleaving can corrupt framing. | Independent RX buffers and timeout state; tests interleaved messages. |
| Arduino firmware | Immediate polarity reversal with no intentional dwell. | Both PWM channels disabled and both wheels held in electrical short brake for a nonblocking 70 ms before reversing either wheel. STOP cancels pending reversal. |
| Arduino firmware | Previous K brake has no durable emergency latch. | Retain K as v1.6.4-compatible ordinary brake. Add X as a distinct, latched E-stop; requires U plus a zero command to resume. K **cannot** release X. |
| Arduino firmware | Motor pin updates sequentially could cause briefly mixed old/new directions. | Disable both channel PWMs before changing either pair of direction pins. |
| Desktop motor mixing | W+S combined with A/D unexpectedly makes a pivot because forward subtracts to zero. | Conflicting forward/reverse is now a full stop, irrespective of steering. |
| Desktop transport | Firmware probe Q write did not have the timeout used for normal motion writes. | 0.85 s timeout for probe to prevent indefinite UART writer lock. |
| Desktop transport | No protocol-level emergency latch or protection from delayed arm/re-stop races. | X command on emergency and initial connection, explicit U + M,0,0 arm, generation counter to ensure a newer emergency wins over an in-flight arm. |
| Desktop app | New BLE connection auto-selected WASD and default boost gear 2=255 PWM. | Connection stays braked until deliberate ACTIVATE WASD; initial real motor driving uses Precision gear 1. |
| Telemetry | New latched emergency state was not recognized. | Support state E as LATCHED EMERGENCY STOP. |

Preserved from v1.6.4: the full GUI, demos, route planning, motor balance, source-dependent mouse/keyboard holds, key-repeat suppression, diagnostics, flight recorder, watchdog, M,left,right protocol, Q/H,13 handshake and stationarity-only SoftwareSerial telemetry.

## Protocol and hardware assumptions

Board: Arduino Uno, TB6612FNG, HM-10 UART at 9600 baud. D4 STBY, D5 PWMA, D6 PWMB, D7 AIN1, D8 AIN2, D9 BIN1, D10 BIN2, D2 RX Bluetooth TX, D3 TX Bluetooth RX (3.3 V level-shift). Common GND required; motor battery connects to VM using an **accessible physical motor battery isolation switch**. A 10 kΩ STBY pulldown to GND is recommended so the driver stays disabled while Arduino pins float at reset.

Positive PWM is assumed to mean **physical forward**, but the default firmware sets `LEFT_MOTOR_POLARITY=1`, `RIGHT_MOTOR_POLARITY=1`. Motor mounting and swapped wiring may require a polarity of -1 on either side. **Never use software PWM telemetry as confirmation of actual wheel direction or RPM.**

New firmwares:
- `M,left,right\n`: two signed integer PWMs (-255..255).
- `K\n`: active brake, compatible with repeated K in the existing BLE bridge. K resets *ordinary watchdog* lockout as in v1.6.4, but never clears X.
- `X\n`: latch the hardware driver in commanded emergency electrical brake (state E).
- `U\n` + `M,0,0\n`: explicit arm sequence after physically inspecting safety. Sending U alone does NOT drive motors.
- `Q\n` gives `H,13` while stationary.

**IMPORTANT:** X is a *software* brake relying on a functioning TB6612FNG; it is NOT a substitute for the motor battery cutoff. HM-10 connection and Arduino firmware must be working. An electrically stuck motor output can move despite correct software.

## Bench checklist, wheels off the ground

1. Motor battery OFF. Check common grounds, motor outputs AO1/AO2 and BO1/BO2, battery VM voltage, STBY, all four direction pins, motor terminal insulation. Disconnect motor battery while uploading firmware.
2. Upload `controller/arduino/MotorTest/MotorTest.ino`. With wheels raised and power switch accessible, open Arduino Serial Monitor at 9600 and send `T`. Six short stages last **650 ms each** with **600 ms short-brake gaps**: LEFT FORWARD, LEFT REVERSE, RIGHT FORWARD, RIGHT REVERSE, BOTH FORWARD, BOTH REVERSE. Use `X` or `S` to abort. The test starts only on explicit T and does not run at boot.
3. Record actual wheel direction and whether BOTH channels stop during every gap. If right reverse/brake fails or wheel spins by itself, immediately switch the motor battery OFF; inspect right motor and TB6612 B channel before further powered tests. Software can neither prove nor repair a damaged output transistor.
4. If an independent wheel spins opposite the commanded positive direction, edit the matching `*_MOTOR_POLARITY` to -1 **in the normal firmware**, not in the test sketch. Switch motor battery OFF again before flashing `BuggyController.ino`.
5. Run full Windows `controller/run.bat`; scan and connect to correct HM-10 FFE1 characteristic, after matching firmware upload. The new bridge sends K and X on connect and requires a **manual** ACTIVATE WASD click to release the emergency latch. Starts Precision Gear 1. Keep wheels raised.
6. Test W, S, A, D, W+A, W+D, S+A, S+D; verify individual and both-wheel directions, absence of sudden direction reversals, plus immediate brake when controls released. **S+A and S+D follow car-style backing steering** (rear displacement), not necessarily the buggy's instantaneous yaw direction. Then press W+S+A and verify neither motor drives.
7. Press ESC/SPACE/STOP during a moving wheel test. Verify X latches and pressing a movement key alone cannot resume motion; all keys must be released and the operator must explicitly re-arm. Disconnect BLE or freeze the app while motors are raised to observe a watchdog stop. Do not place fingers near powered wheels.
8. Only when **every** step passes perform a careful, slow ground test in a clear supervised area. Route timing and turning radii are open-loop estimates, not autonomous navigation.

## Tests provided / limits

- Windows: run `controller/offline_tests.bat`, or from `controller` directory `python -m pytest -q`.
- Existing C++ firmware mocking tests updated for 70 ms reversal deadtime and six abortable motor-lab stages.
- New `test_wheel_safety_v165.py` checks conflicting WASD keys, E telemetry, BLE X/U sequence, and only allowing driving after deliberate rearm.
- CI workflow compiles both Arduino Uno sketches and runs Python/C++ tests under Xvfb. **CI must show GREEN and/or be independently verified; previous attempts on this GitHub account returned failing jobs with no accessible logs. Do not claim compilation passed until checks actually pass.**
- No encoder, IMU, wheel-current sensor or tachometer is available: software cannot verify actual right-wheel rotation, speed matching, or braking force.
- This PR does **not** overwrite the hosted v1.6.4 ZIP or deploy the untested candidate to the team site. The production downloadable ZIP is still the original historical release, and should not be confused with this GitHub branch.

## Release gate

Do not merge, publish downloads, deploy to the team's site, or permit floor driving until native firmware compilation, regression tests, and the complete physical right/left channel checks have passed. Preserve the old known working files for rollback.
