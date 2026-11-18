# CABBAGE Control Studio v1.8 — Premium Operator Interface (development candidate)

**New in v1.8:** redesigned Drive / Routes / System workspaces; a nine-direction hold-to-drive cockpit; large live left/right PWM command diagram; link-path visualization; atomic pointer release; live-tuning safety brakes; validated Save/Reset Tuning; Power Path Lab for Bluetooth power loss on batteries; Quick Preflight; searchable Operator Guide; and a test-only Windows EXE build workflow.

**First launch (Windows):** Use `demo.bat` to explore with no motors or BLE connection. Use `run.bat` to open the Bluetooth-enabled controller only once physical power and wiring have been inspected. The root window starts on the **Drive** workspace, and hardware movement always needs a deliberate arm. Hold the direction pad or W/A/S/D; release to brake. Press ESC/Space or the red Emergency Stop at any point. F1 opens Wheel Doctor. The **System** workspace includes Quick Preflight, Power Path Lab, full BLE diagnostics and a searchable Operator Guide.

**Testing:** Open `offline_tests.bat` or use **System → Quick Preflight** while offline to run the pin/protocol, control-math and synthetic BLE link checks. `PIN_AUDIT.bat` checks source wiring declarations without energizing any hardware. The **Windows candidate packaging** GitHub Actions run builds `Cabbage-Studio-v18-CANDIDATE.exe` as an artifact for Windows; the branch also retains the `build_windows_candidate.bat` local build launcher. Neither a successful Windows build nor passing tests proves real motor rotation or braking.

**Design review and detailed operator guidance:** [V18_DESIGN_AUDIT.md](V18_DESIGN_AUDIT.md) and [WHEEL_DOCTOR_FIELD_GUIDE.md](WHEEL_DOCTOR_FIELD_GUIDE.md).

**Safety status:** Experimental, unmerged and not validated on the actual buggy. The old production release is untouched. Do not assume HM-10 VCC tolerates 5V, and do not mistake a USB-powered Arduino LED or firmware PWM feedback for a validated motor supply or wheel sensor. Keep the motor power switch accessible and raise both wheels for preliminary testing. Never rewire under power.

---

## Historical v1.7 Wheel Doctor documentation

# Buggy Control Center — v1.7 Wheel Doctor Field Lab (development candidate)

**This is an unmerged candidate built on the v1.6.5-safety pull-request branch, not the stable v1.6.4 download. No one has certified these changes on a physical buggy. Do not drive on the floor until both independent wheels and braking pass the physical check.** Keep your existing v1.6.4 files for rollback.

### New guided diagnosis

- Press **F1** or click **PIN + WHEEL HELP [F1]** at the top of the Windows GUI to launch **Wheel Doctor**.
- **SOURCE PIN AUDIT** cross-checks both Arduino sketches, Uno D4–D10, SoftwareSerial D2/D3, the Windows BLE packet order and firmware motor A/B mapping. This checks source code only, **not real wires**.
- **PROBE FIRMWARE** asks for a **V,165** response. If missing, app-driven motor pulses stay disabled to protect against older firmware without the X-latch protocol.
- Only with **wheels raised**, immediate **physical motor-battery cutoff** and both safety confirmations can you click an individual **TEST 0.45s** button. Each pulse is limited to PWM 150 and requests **K + X braking**, with Escape/Stop cancelling it. Bluetooth delays/watchdog mean the physical switch is still necessary.
- Record human-observed LEFT/RIGHT FORWARD/REVERSE + BOTH results, click **DIAGNOSE RESULTS**, then COPY or SAVE the fault report. Without wheel sensors, the app cannot declare any actual wheel passed based on telemetry.
- If Bluetooth is unreliable or the firmware version cannot be checked, flash the standalone **MotorTest.ino** and send individual digits **1–6** in Serial Monitor (9600 baud). **T** runs all six; **X/S** abort. Restore the main firmware afterwards.
- The ordinary **DIAGNOSTICS** window also now performs an automatic code-level source audit, with an expanded physical pin checklist.

Start here for wiring, isolation, compatibility and safety: **[WHEEL_DOCTOR_FIELD_GUIDE.md](WHEEL_DOCTOR_FIELD_GUIDE.md)**.

### How to run and check (not hardware certification)

Install Python 3.11+ with Tkinter. On Windows run `run.bat` for real BLE or `demo.bat` for a no-motor simulation. From the `controller` folder run `python -m pytest -q`. Arduino Uno compilation is checked by GitHub Actions if the workflow succeeds. Replace the Uno sketch with this branch's `arduino/BuggyController/BuggyController.ino` only after powering OFF the motor battery. Existing older firmware deliberately cannot use the new GUI's live pulse test.

---

## Historical v1.6.4 controller documentation (stable release)

# Buggy Control Center v1.6.4 — Drive Priority

This is the complete Windows desktop controller **and** matching Arduino Uno firmware for the TB6612FNG/HM-10 buggy. Built on v1.6.3 with a safer command-first UART policy, bounded BLE writes, offline link stress simulation and Precision drive. See `CHANGELOG_v1.6.4.md` for the current changes.

**Hardware has not been tested in this release.** The original problem could also involve the right-hand motor, TB6612FNG B-channel, power supply, or wiring; passing a software test cannot prove the wheel turns or brakes.

## Install on Windows

1. Extract the **whole ZIP** to a new folder; don't mix files from older versions.
2. If you only want to practice without the buggy, double-click `demo.bat` (no hardware or actual BLE used).
3. To use the actual buggy later, turn **off and disconnect the motor battery** first. Plug the Uno into USB and upload `arduino/BuggyController/BuggyController.ino` via Arduino IDE. **Upload the included v1.6.4 firmware for drive-priority telemetry and watchdog lockout. The GUI also parses the older H,13 protocol and older telemetry packets.**
4. Disconnect Arduino IDE Serial Monitor and USB if necessary, then power normally. Raise both wheels off the ground for the first tests and keep the motor-battery switch accessible.
5. Double-click `run.bat`, disable Demo, scan and connect to HM-10 / `cabbagelover` (possibly advertised as `HMSoft`), choose UART characteristic `FFE1` if appropriate.
6. Click **ACTIVATE WASD** after releasing all keys. Test short W / S / A / D holds at Gear 1, then release to brake; test Space or Escape emergency braking. Escape works even when a text field is focused; Space must remain available when entering custom routes. If a key becomes blocked after an emergency stop, **release all movement keys, then click ACTIVATE WASD** to re-arm.

You can also run `offline_tests.bat` with no buggy. It exercises GUI behavior, transport simulations and Python tests. A C++ firmware simulation is run if `g++` is installed; otherwise that optional test is skipped. Test dependencies are separate from the normal app.

## New in v1.6.4

- **Drive-priority HM-10 UART:** While either motor is commanded to move, the Uno no longer transmits optional `SoftwareSerial` telemetry or a handshake reply. Half-duplex transmit was a credible cause of missed incoming drive packets. Telemetry resumes after braking. *You will not receive live Arduino PWM acknowledgements during movement by design.*
- **Arduino received-command counter:** With v1.6.4 firmware, each stationary telemetry packet includes a cumulative count of accepted `M,left,right` frames: `T,left,right,state,seq,count`. The GUI displays `RX CMD n` and records the count in the CSV. Older five-field telemetry is still supported. A count proves firmware parsed a command, **not that the wheel physically rotated**.
- **Post-watchdog re-arm:** If 1.2 seconds pass with no valid drive packet, the Arduino actively brakes and refuses more nonzero `M` packets until it receives `K` or `M,0,0`. This prevents an old held-key stream from abruptly restarting after a radio outage. Release controls, verify the buggy is safe, then press again.
- **Bounded BLE writes:** A GATT write stalled for more than 0.85 seconds triggers a link error and disconnect instead of blocking the sender indefinitely. The hardware watchdog remains the last-resort protection if BLE fails. Motors should be stopped using the physical power switch if they move unexpectedly.
- **Less idle BLE chatter:** Motor commands remain every ~120 ms; braked heartbeat is every ~300 ms, with an immediate prioritized brake on release/Space.
- **Precision drive:** A manual-only checkbox selects usable lower gear levels `110 / 150 / 200 / 240`. Unchecked retains your requested boosted gear profile `220 / 255 / 255 / 255`. Changing this mode while moving brakes the buggy and requires a fresh key release and press; automatic-route gears are unaffected.
- **OFFLINE LINK STRESS:** Deterministic virtual 20-second cases with packet jitter, simulated losses and a 2-second outage. Demonstrates expected watchdog and lockout behavior; **not a test of your actual Bluetooth adapter, batteries or motors**.
- **Escape safety shortcut:** Escape now brakes even when a track text field has focus; Space still works outside text fields. This permits normal editing of commands such as `F 50`.

## Previous improvements in v1.6.3


- **Windows key-release confirmation:** transient Tk synthetic KeyRelease events no longer stop a physically held movement key; Space emergency-brake latch cannot be defeated by these repeats. Lost genuine key releases still stop after confirmation.
- **Command Flight Recorder:** the app records input presses/releases, successful BLE writes (actual packet payload and write latency), Arduino PWM acknowledgements, safety brakes and link failures, up to the most recent 6,000 events. Click **EXPORT TRACE CSV** after stopping to save a diagnostic trace. Times are UTC plus monotonic elapsed seconds. BLE accepted writes and Arduino PWM acknowledgements are **not** proof of physical wheel motion.
- **Link health indicator:** shows time since the most recently accepted GATT write and approximate BLE write duration; a stale warning appears after 0.6 seconds without a successful write. It does not prove the Arduino received the message.
- **OFFLINE CONTROL CHECK:** tests 42 control calculations, including independent reverse channels and speed bounds, without issuing BLE drive commands. For safety, this is available when disconnected or in Demo mode.
- **Manual motor balance:** optional −30%..+30% adjustment. Positive balance favors the right wheel by slowing the left motor; negative balance favors the left by slowing the right. Default is 0%, automatic tracks are unchanged, and this cannot repair a dead right motor or driver channel.
- **UI-stall safety stop:** after an unexpectedly long GUI pause (>1.4 seconds), a previously active drive is braked rather than resumed from stale key input. Release keys and re-arm WASD.
- **Firmware handshake:** reply to Q is deferred until the SoftwareSerial UART is quiet, reducing dropped inbound drive bytes. The H,13 response remains compatible with existing diagnostics.
- **Motor Channel Lab:** the standalone `arduino/MotorTest/MotorTest.ino` now remains braked after reset until you type **T** in Serial Monitor (9600 baud). It tests LEFT and RIGHT, forward and reverse independently. **This is NOT the main Bluetooth firmware**; restore `BuggyController.ino` after the bench test.
- Removed the old **Braking Strength** slider, which was misleading because release always commands an immediate active brake.
- `run.bat` skips dependency installation if already present; `demo.bat` runs offline without needing Bleak.

## What was fixed

- Incoming **Arduino `SoftwareSerial` UART** now takes priority over periodic outgoing telemetry; telemetry is sent approximately once a second, only after a quiet receiving interval. This reduces half-duplex packet interference. Driver watchdog remains **1200 ms**.
- The Arduino parser recovers from truncated `M,left,right` packets on a fresh `M` and prioritizes an emergency `K` brake **even during an incomplete packet**. Drive commands through BLE must use framed `M,left,right\n` packets; stray legacy single characters are no longer allowed to start a wheel. Legacy single-byte diagnostics are still available over USB Serial.
- A motor commanded to **0 PWM while the other wheel moves now brakes**, rather than freely coasting; both zero commands also brake both motors. This is a change to how slow/pivot steering behaves.
- BLE writer reads the **latest** desired PWM/brake state after obtaining its write lock, reducing delayed stale-command pulses. An old urgent-brake task cannot override a later fresh keypress.
- Manual **keyboard and on-screen mouse button holds are tracked separately**. Releasing one no longer cancels the other. Windows synthetic key-up/key-down pairs cannot prematurely unblock a brake latch.
- **ACTIVATE WASD** can recover after a missed release *when no physical WASD keys are still down*. GUI warns if Arduino telemetry disagrees with manual PWM or reports a watchdog stop. Telemetry is **command acknowledgement**, not a wheel-speed sensor.
- The existing automatic route logic, pin mapping, active brake, diagnostics and speed gears were retained. **Gear 1 = 220 PWM, gears 2–4 = 255 PWM** (255 is the maximum; the higher three gears are therefore equal). Note that full PWM can place a large load on weak battery packs.

## Wiring reference

| Arduino Uno | TB6612FNG | Arduino Uno | HM-10 |
|---|---|---|---|
| D4 | STBY | D2 (RX) | TXD |
| D5 | PWMA | D3 (TX) | RXD via 5V→3.3V divider |
| D6 | PWMB | 3.3V | VCC *only if the module breakout requires 3.3V* |
| D7 | AIN1 | GND | GND |
| D8 | AIN2 | | |
| D9 | BIN1 | | |
| D10 | BIN2 | | |
| 5V | VCC | | |
| GND | GND | | |

TB6612FNG **VM** is the switched motor-battery positive. Battery negative, TB6612FNG GND and Uno GND are common. **AO1/AO2 → left motor, BO1/BO2 → right motor.** Motor polarity depends on physical mounting.

A **10 kΩ pulldown resistor from STBY to GND** helps keep the driver disabled during Uno reset / sketch upload. Keep D4 connected to STBY as well. Do not power the motor driver via Uno 5V in place of the VM battery supply.

## First real-hardware check

1. Upload with motor battery disconnected and **never** while wheels are touching the floor.
2. Confirm both wheels are stationary on startup and on BLE connection (no command issued).
3. Check **Precision drive** to start at low PWM, then briefly hold W in Gear 1; release it. After stopping, the Arduino should report `ACTIVE BRAKE` and the `RX CMD` counter should have increased. Do the same for S, then press Escape or Space while moving. The GUI deliberately pauses live Arduino feedback during motion in v1.6.4.
4. If the **right** wheel still spins by itself or fails to brake, **cut battery power**. This release cannot rule out a failing TB6612FNG B channel, wrong BO1/BO2 wiring, a short or a weak/incorrect power supply. The separate `arduino/MotorTest/MotorTest.ino` can help isolate motor wiring, but use only with wheels raised.
5. If BLE says connected but motor drive stops after a while, release all movement keys. After it is stationary, look for **DRIVER STATE: WATCHDOG BRAKE** or an increased `RX CMD` counter; the event log and CSV trace can reveal command gaps. The firmware will not automatically restart driving after a watchdog trip until a stop/re-arm. Send the exported trace if debugging is needed. Check whether Arduino USB power remains stable under load. A motor overload can cause voltage dips and intermittent resets.

## Limits and safety

- No wheel encoders are installed. The app cannot measure true RPM, direction, rotation, braking distance or motor current; its PWM bars are **commanded values only**.
- Software is **not** an independent emergency stop. Use a real battery switch. The motor driver must be correctly wired and functional for active short braking to operate.
- An Arduino reset makes control pins briefly high-impedance; the firmware cannot stop what happens *before* its `setup()` runs. The hardware STBY pulldown is important.
- Live firmware has **not been compiled with an official Arduino board toolchain or tested on your physical Uno**. The included host simulator compiles the core `.ino` with mocked Arduino functions and checks pin commands.

## How to interpret the flight recorder

1. If WASD does not register in the GUI or the trace has no `INPUT` rows, diagnose keyboard focus/event handling.
2. If `INPUT W_DOWN` appears but `BLE_TX M,...` is missing or delayed, suspect the PC BLE write path. `BLE_TX` means Windows accepted the write, **not** that the Arduino got it.
3. If BLE writes are present but no `ARDUINO_RX` telemetry arrives, check HM-10 notifications, RX/TX wiring, correct firmware, and baud. Some clones cannot notify; absence of telemetry alone does not prove failure.
4. If the Arduino telemetry shows matching positive or negative PWM for both motors but only the left wheel rotates, check the TB6612FNG B-channel, VM supply under load, motor wiring and right motor. **Telemetry has no wheel sensor.**
5. Use the separate Motor Channel Lab (upload with motor battery disconnected; wheels raised, send `T` in Serial Monitor) to test right forward and reverse without BLE.

**Safety:** active brake is only an electrical command and depends on a functional motor driver and battery supply. The physical motor-battery switch remains the reliable way to remove power. A 10 kΩ STBY pulldown is recommended to keep the driver disabled while Uno pins float during reset/upload.
