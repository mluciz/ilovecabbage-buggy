# Wheel Doctor Field Lab — v1.7 candidate (18 November 2026)

**Status: development branch, not hardware certified and not a released downloadable Windows build.** The Windows app, firmware and motor-test sketch must be updated together. Preserve your old copy for rollback.

## Five-minute no-motion diagnosis

1. **Motor battery OFF.** Open the app and choose **WHEEL DOCTOR** (or F1). Choose **SOURCE PIN AUDIT**. A PASS verifies the two Arduino source pin declarations and the Windows left/right UART packet mapping, **not** physical continuity.
2. Compare the printed pin map with **your real wires**. Unplug the motor battery before moving connectors. Check STBY, VM and shared GND, especially the TB6612 B/right motor output. Verify motor-battery switch operation.
3. Run **PROBE FIRMWARE** after connecting HM-10. Only the candidate sketch replies `V,165` and enables app-driven short pulses. The existing `Q` → `H,13` handshake is too old to prove X/U emergency-stop compatibility.
4. Lift **both wheels** clear of surfaces and hands, have physical motor power cutoff reachable, and tick the two safety checkboxes. Click exactly **one** specific direction's **TEST 0.45s**. Each click opens a separate final confirmation. It sends max absolute PWM 150 for a ~450ms command window and requests K + X stop afterwards. Transport delays can extend physical movement; only the battery switch is a dependable hard cutoff.
5. After each test, choose what **you saw**: PASS / NO MOVEMENT / WRONG DIRECTION / OTHER WHEEL MOVED / FAILED TO BRAKE. Choose **DIAGNOSE RESULTS**. Save/copy the report to troubleshoot with evidence. A failed brake is an immediate **power-off** condition.
6. If app pulses cannot run, install `arduino/MotorTest/MotorTest.ino` with battery disconnected; launch Serial Monitor at **9600 baud**. Send digit **1** to test only left forward, **2** left reverse, **3** right forward, **4** right reverse, **5** both forward, **6** both reverse. Each runs **650ms** and brakes automatically. Type **X** or **S** to abort, or **T** to run the full six-step sequence. Restore `arduino/BuggyController/BuggyController.ino` after debugging. This isolates the Bluetooth/Windows app from Arduino-to-driver/motor hardware.

## Actual source pin and signal map

| Uno | Physical TB6612FNG/HM-10 terminal | Function |
|---|---|---|
| D4 | STBY | Driver standby enable, with recommended 10k pulldown |
| D5 (PWM) | PWMA | LEFT motor A channel speed |
| D6 (PWM) | PWMB | RIGHT motor B channel speed |
| D7 | AIN1 | LEFT direction 1 |
| D8 | AIN2 | LEFT direction 2 |
| D9 | BIN1 | RIGHT direction 1 |
| D10 | BIN2 | RIGHT direction 2 |
| D2 (software RX) | HM-10 TXD | UART into Arduino |
| D3 (software TX) | HM-10 RXD via logic-level divider | Prevent 5V logic to 3.3V HM-10 input |
| 5V | Driver VCC | TB6612 logic supply only |
| switched battery + | Driver VM | Motor supply (never Uno 5V) |
| GND | Driver GND, battery -, HM-10 GND | Common ground |

LEFT motor uses AO1/AO2; RIGHT motor uses BO1/BO2. Actual wiring may have been swapped. The exact HM-10 module VCC requirement varies by breakout; do not assume every module tolerates 5V. The UNO is not a BLE device itself; the HM-10 bridges BLE GATT to 9600-baud software serial.

**Source audit checks:** expected Uno PWM pins, no duplicate control pins, pin declarations in BOTH sketches, SoftwareSerial RX=2/TX=3, left/right packet order from app through bridge into firmware, and A/B PWM output mapping. It cannot read or visually confirm physical wiring. Use a multimeter and the real device for VM/STBY/VCC checks.

## Evidence guide

| Evidence | What it proves | Next layer |
|---|---|---|
| App key/button highlights | Windows received input | GUI active keyboard state |
| BLE connected | Windows opened a Bluetooth link | GATT property / UART characteristic |
| GATT write accepted | Windows BLE stack accepted bytes | HM-10 RX/TX wires |
| Q → H,13 | Some compatible Arduino UART protocol replied | Firmware capability V,165 |
| V → V,165 | Candidate firmware answered version query | TB6612 control pins and power |
| RX CMD increments while stopped | Arduino parsed motor frames | driver outputs, motor wiring |
| One wheel actually rotates | User-observed physical movement | polarity, braking, load |

**No encoder, motor-current sensor or motor VM-voltage sensor is installed.** PWM bars and firmware telemetry **cannot** prove the wheel physically rotated.

## Rapid isolation rules

**Neither wheel moves:** with motor power OFF first, check motor switch/battery wiring to VM and common ground. Confirm driver VCC 5V and STBY D4 connection; safely measure voltages only if trained and not reaching near spinning parts. Uno powered from USB does NOT imply VM has motor voltage.

**Only right wheel fails in both directions:** inspect D6 (PWMB), D9/D10 (BIN1/BIN2), driver B channel, BO1/BO2, right motor wires, and motor itself. A bad motor, broken output wire or damaged TB6612 channel can look like a software error.

**One direction fails:** verify right/left direction-input pair and actual motor terminal connections. A low duty cycle may also fail to overcome static friction. Do not increase PWM blindly if any channel is unsafe.

**Wrong physical direction:** double-check mounting, motor polarity and port assignment; only then edit `LEFT_MOTOR_POLARITY` or `RIGHT_MOTOR_POLARITY` in the main firmware and reflash with motor supply OFF. The standalone motor-test sketch uses raw channel polarity, not the correction constants.

**Wrong wheel moves:** physical AO/BO outputs may be swapped. Do not fix by swapping app's left/right packet fields without tracing the wiring first.

**Firmware replies but motor stays still:** RF path is probably working, not necessarily motor power. Use isolated MotorTest from USB to rule out BLE and app; do not treat PWM feedback as wheel movement.

**Wheel keeps moving after stop, or reverses unpredictably:** cut motor battery immediately, stop all testing and inspect the driver, shorts and power switch. A software X stop cannot force a failed driver transistor to brake.

## Compatibility and safety

- Windows 10/11 with Python 3.11+ and Tkinter; install the `controller/requirements.txt` packages by using `run.bat`. BLE uses Bleak and a working Windows Bluetooth Low Energy adapter. The current UI is not a phone APK.
- Arduino Uno and TB6612FNG with HM-10-like BLE UART, normally FFE1. Some clones have different writable/notifiable GATT characteristics or power/logic requirements. Some clones do not support notifications, so **app-driven pulses remain disabled without V,165**; the serial-only MotorTest is the fallback.
- Legacy v1.6.4 firmware lacks V,165 and X-latched E-stop. Do not bypass the version guard.
- No automated route or normal WASD driving while a bench pulse is active; Escape/Stop cancels an in-flight pulse at the next bridge safety check. The motor watchdog is 1200ms; the physical switch remains essential.
- This candidate is not field-proven. Keep the wheels raised for every early validation. Do not merge or overwrite production ZIP until C++ mock tests, real Uno compilation, Windows GUI tests, physical wiring verification and both-channel brake tests have passed.

## Offline checks

From the `controller` directory:

```shell
python -m pytest -q
python -c "from wheel_doctor import audit_sources; ok, lines = audit_sources(); print('\n'.join(lines)); raise SystemExit(0 if ok else 1)"
```

To compile for a real Arduino Uno with `arduino-cli`:

```shell
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:uno arduino/BuggyController
arduino-cli compile --fqbn arduino:avr:uno arduino/MotorTest
```
