# ilovecabbage 🥬 — Buggy Wheel-Control Safety

This repository started with only a README. This branch adds actual Arduino and Windows controller source recovered or reconstructed during the **11 November 2026** wheel-control safety audit. The original Windows Control Center v1.6.4 ZIP is *not in this GitHub repository*, and its full historical GUI source has not been audited here.

## What's included

- **Arduino Uno firmware:** [BuggyController.ino](controller/arduino/BuggyController/BuggyController.ino), v1.6.5-safety. Retains signed \`M,left,right\\n\`, K stop, Q handshake \`H,13\`, watchdog, and active TB6612FNG braking. Adds independent USB/BLE parsers, two-channel direction-change interlock and optional latching X emergency stop/U unlock.
- **Hardware calibration sketch:** [MotorTest.ino](controller/arduino/MotorTest/MotorTest.ino), with six separately labelled wheel tests and serial abort.
- **Simple alternative Windows BLE controller:** [controller/app.py](controller/app.py) (Tkinter + bleak). This is not the unverified historical route-planning app.
- **Regression tests:** Python motion mixer tests and native C++ firmware simulation, plus Arduino Uno build CI.
- **Safety analysis and wiring:** [docs/WHEEL_SAFETY_AUDIT.md](docs/WHEEL_SAFETY_AUDIT.md).

## Getting started (wheels off the floor)

1. Read [the safety audit and six-step calibration procedure](docs/WHEEL_SAFETY_AUDIT.md).
2. Turn OFF motor battery and upload \`controller/arduino/MotorTest/MotorTest.ino\` to an Arduino Uno. Lift wheels, switch power on, send \`T\` at 9600 baud, and verify **both directions on both motors**, particularly right reverse and braking. Turn off motor battery if any wheel behaves unpredictably.
3. Only if all six tests pass: verify/update \`LEFT_MOTOR_POLARITY\` and \`RIGHT_MOTOR_POLARITY\` in the normal firmware, switch motor power OFF, then upload \`controller/arduino/BuggyController/BuggyController.ino\`.
4. On Windows with Python installed, run \`controller\\install.bat\` once and \`controller\\run.bat\` to launch the minimal BLE controller. Scan for your HM-10 / HMSoft device, connect, then explicitly ARM before trying WASD or the on-screen direction controls.
5. Start with wheels still lifted. Check forward, reverse, pivot turns, gentle arc turns, STOP, latched E-STOP, Bluetooth loss and actual wheel rotation before any floor test.

**No physical driving is certified by software tests.** A faulty right TB6612FNG channel, bad motor wiring, unsuitable battery supply, absent common ground or wrong wheel polarity can make motion unreliable even when the code builds and simulation passes. Keep a physical motor-battery cut-off accessible.

## Protocol

\`M,<left>,<right>\\n\` where each signed power is an integer from -255 to +255. Zero commands active short-brake. \`K\` brakes and requires a subsequent \`M,0,0\` before nonzero motion. \`X\` latches emergency stop; \`U\` unlocks that latch, and a zero frame is still required before driving. \`Q\` returns \`H,13\`. Legacy USB-only F/B/L/R commands remain for bench diagnosis. Do not send single-byte legacy motion over BLE.

## Tests

\`\`\`shell
python -m unittest discover -s tests -v
g++ -std=c++17 -Wall -Wextra -Werror -Itests/arduino_stubs tests/firmware_harness.cpp -o /tmp/firmware-harness
/tmp/firmware-harness
\`\`\`

GitHub Actions also compiles the sketches for \`arduino:avr:uno\`.

Historical hosted website: https://buggy-team-hub.vercel.app . Its download ZIP and advanced Windows GUI are not included in this repository and should not be treated as reviewed by this PR.
