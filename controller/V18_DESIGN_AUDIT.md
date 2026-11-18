# CABBAGE Control Studio v1.8 — Design and Safety Review

**Status:** Development candidate on a stacked pull request. The v1.6.4 production download is preserved, and the v1.7 Wheel Doctor development branch is preserved. This is not a physical-device certification or evidence of successful wheel rotation.

## Architecture / UX issues found and addressed

| v1.7 issue | v1.8 change | Validation |
|---|---|---|
| Manual drive, route planning, telemetry and troubleshooting squeezed into a continuous desktop layout | Separate **Drive / Routes / System** pages, a persistent left navigation rail and top-level emergency stop | Tk GUI regression tests (page creation / navigation / active view) |
| PWM values hard to interpret as real vs requested | Large vector-drawn two-motor chassis, direction-coded labels, explicit **COMMAND NOT RPM** legend, plus Windows→BLE→Arduino link diagram | Pure motor label tests and GUI render tests |
| Pointer controls limited to WASD and diagonals required holding two inputs | Nine-position mouse-friendly hold pad including four diagonal combinations and a central brake | Atomic diagonal press and release tests |
| Pointer release away from button could leave a held mouse input or briefly pivot | Global pointer release now atomically clears mouse-held keys, preserves genuine keyboard-held input and sends just one updated motor frame | Regression tests for mouse/keyboard overlap and missing local release |
| Changing gear/steering/balance during movement could abruptly shift PWM | Revoke active real drive on live tuning changes; require deliberate re-arm | Live tuning / automatic route safety tests |
| Gear shortcuts could affect non-drive page; naive fix blocked route text digits | Separate normal text input from drive-key processing, then restrict live shortcuts to Drive only | Tests for entry typing and non-drive shortcuts |
| Operator had to retype tuning | Save / reset explicit preferences, validated and atomically written to AppData / XDG config | Round-trip / corruption / unsafe-field exclusion tests |
| No clear path when HM-10 works on USB but not batteries | **Power Path Lab** with source-comparison workflow and self-reported checks | Pure fault-tree tests, no false electrical measurements |
| Offline tests scattered across buttons | **Quick Preflight**, one-click aggregate source pin audit + control math + synthetic BLE stress, save or copy report | Previous individual checks retained |
| Running as source requires Python and packages | Windows build workflow makes an optional test-only PyInstaller EXE, while .bat launchers remain | Windows CI packaging job |
| Firmware/app mismatch can make diagnostics unsafe | v1.7 **V,165** query required before guarded app motor pulses; isolated MotorTest sketch remains | Existing firmware mock, BLE tests, Arduino Uno compilation |

## Operator workflow (Windows)

1. Download and unzip this branch (or the **candidate EXE** from the Windows build's GitHub Actions artifacts).
2. If using Python source: run `controller/demo.bat` to explore the interface without any Bluetooth or motors. `controller/run.bat` opens the hardware-capable application.
3. **Drive:** Choose SIMULATOR and CONNECT to explore. Select 1–4 gears; steering and left/right balance are adjustable. Drive via W/A/S/D or hold the large eight-direction pad. Releasing input brakes. Press ESC or Space, or use the red emergency button.
4. **Routes:** Edit track geometry or custom commands and PREVIEW. These are open-loop estimates, not sensor-measured navigation. Do not run on the physical ground until wheel/brake checks have passed.
5. **System:** Open Power Path Lab for USB-versus-battery issues; Wheel Doctor for six actual wheel-motion observations; Full Diagnostics for BLE/UART; or Quick Preflight to run source/synthetic checks while disconnected.
6. **Save Tuning:** Stores gear, precision, steering, balance, UART UUID, measured speed and wheel spacing. **Never stores** drive arming, current motor intent, BLE target address or automatic reconnection. Re-arming must always be explicit.
7. **Physical bench verification:** Before touching wiring, isolate motor battery power. Confirm actual Uno D2/D3 UART wiring, D4–D10 driver pins, common ground, TB6612 VM, HM-10 power requirements, and physically raise both wheels. Test one motor direction at a time. If any wheel does not stop, cut motor power.

### Connection truth table

- **Windows display receives WASD:** A UI event, *not* evidence of BLE connection.
- **BLE write accepted:** Windows Bluetooth stack accepted a GATT command, *not* that the Arduino decoded it.
- **UART firmware reply:** Arduino answered, *not* that the driver energized the right channel.
- **Arduino commanded-PWM telemetry:** Electrical *intent* only, *not* actual output voltage, wheel RPM, wheel traction or stopping distance.
- **Eye observes wheel spin:** Physical rotation evidence, but still not a motor RPM measurement. Confirm both directions and stopping separately.

## Open physical risks and limits

- The current buggy has no wheel encoders, motor current sensors, motor battery-voltage telemetry or autonomous obstacle sensing integrated into this controller.
- The actual HM-10 VCC rating differs between bare 3.3V modules and regulator-equipped breakout boards. Do **not** move the module's supply to 5V based on its LED status alone.
- **USB works, battery fails** likely requires voltage measurements at the module VCC and Uno 3.3V rail with the correct battery/driver topology. A software change alone cannot solve an unpowered 3.3V rail.
- The limited-duration BLE motor pulse uses software timing and watchdogs. Bluetooth congestion can delay a stop, and neither stop nor Arduino acknowledgement proves physical braking. Physical motor battery cutoff must remain within immediate reach.
- Windows packaging CI proves an EXE was assembled, **not** that it connected to a specific HM-10 clone or controlled a real motor successfully.
- v1.8 remains a **draft / test candidate**, and should not overwrite production `main` until on-device testing and all software checks pass.

## Validation locally

From `controller`:

```powershell
py -m pip install -r requirements.txt pytest
py -m pytest -q
py -m compileall -q .
```

Official Uno sketch compile (with `arduino-cli`):

```powershell
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:uno arduino/BuggyController
arduino-cli compile --fqbn arduino:avr:uno arduino/MotorTest
```

For one-click offline source checks use `PIN_AUDIT.bat`, or `offline_tests.bat` for the whole Python suite. The CI workflows additionally run a Linux Xvfb GUI test and a Windows candidate packaging build.

The v1.7 pin-by-pin and wheel fault reference remains in **[WHEEL_DOCTOR_FIELD_GUIDE.md](WHEEL_DOCTOR_FIELD_GUIDE.md)**.
