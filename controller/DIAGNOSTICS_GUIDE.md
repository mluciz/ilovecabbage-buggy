# Buggy Control Center 1.6.2 — Diagnostics

The **DIAGNOSTICS** button is at the top of the Windows desktop app. It opens a separate diagnostics window without replacing the manual controls, track planner, brakes or steering slider.

## Start here

1. Install dependencies by double-clicking `run.bat` on Windows. Allow the first install to complete. If Windows cannot find Python, install Python 3.11 or newer with Tkinter from python.org.
2. Upload `arduino/BuggyController/BuggyController.ino` **v1.6.4** to the Uno using Arduino IDE and the correct USB COM port. Older firmware may not support the safe motor-command protocol or handshake.
3. Power the HM-10 and Arduino. Set **Demo mode OFF**. Choose **SCAN BLE**, select your HM-10 from the dropdown (perhaps named **HMSoft** instead of `cabbagelover`).
4. Click **DIAGNOSTICS** > **RUN FULL DIAGNOSIS**. If a device has already been selected, diagnostics rescans and safely attempts to connect to *that selected* device; it never connects to an arbitrary unknown device. If no device was selected, it scans and asks you to choose one, then run again.
5. Read the layer-by-layer status and **SUGGESTED NEXT FIX**. Use **COPY REPORT** or **SAVE REPORT** to share the results for troubleshooting.
6. Click **TEST KEYBOARD**, then press W/A/S/D or 1–4 while the diagnostics window has focus; motor commands are suppressed during this test.
7. Click **WIRING CHECKLIST** to record *your own* physical checks; these are not electronic measurements.

**Safety:** Full diagnosis does not intentionally turn the wheels. It sends a TB6612FNG active-brake command and a harmless firmware query, and retains the brake until a new drive key is pressed after testing. Place the buggy with its wheels raised when diagnosing motor faults. Active braking depends on the driver being properly powered and connected; it is not a substitute for a physical power-off switch.

## What each stage really proves

| Stage | Evidence | What it does **not** prove |
|---|---|---|
| Python / BLE dependency | Python import succeeded | Working adapter hardware |
| USB COM ports (optional) | Windows exposes a candidate serial port | Uno firmware uploads / Arduino powered on battery |
| BLE scan | Nearby advertising BLE devices were seen | HM-10 is necessarily one of them |
| Target discovery | The selected device was seen on a fresh scan | The selected device is necessarily the HM-10 |
| BLE link | A GATT connection was established | Data was received by the Arduino |
| GATT write | Characteristic is writable | Physical UART has been wired correctly |
| Notify | Subscription to BLE notifications succeeded | Arduino code is generating valid data |
| Write | GATT write accepted by the Bluetooth stack | Arduino actually executed the command |
| Firmware | Arduino H,13 protocol replied **`H,13`** to **`Q`** over HM-10 UART | Motors receive power |
| Telemetry | Valid `T,left,right,state,seq` frames arrived | Actual RPM, wheel motion or battery voltage |
| Keyboard | Tk received a key event | Bluetooth communications or motor action |
| Hardware checklist | Only the user's self-reported checks | Electronically verified measurements |

`PASS` means the particular software-observable check passed. `WARN` is a limitation or a partial failure. `FAIL` means a test failed. `SKIP` means it was not possible to reach that stage. `MANUAL` requires human verification; optional USB detection is not required for driving over BLE.

## Common situations

**Scan fails outright:** Enable Windows Bluetooth, check Device Manager, update the BLE adapter driver, and try again. The app records the underlying error.

**Scan succeeds, HM-10 absent:** Confirm module power, distance, advertised name, that no phone is connected to it, and whether it is actually an HM-10-compatible BLE peripheral. Try scanning after power-cycling the HM-10.

**BLE connected, wrong GATT characteristic:** Some HM-10 variants/clones differ. The report lists discovered GATT UUIDs and properties. Enter the writable UART characteristic UUID into the main window and reconnect. Genuine HM-10 modules often use FFE1.

**Link / writes pass, no firmware reply:** Check that v1.6.4 was uploaded, that Uno D2 receives HM-10 TXD, Uno D3 goes to HM-10 RXD through a proper 3.3V level shifter, that both share ground, and UART baud is 9600. **Older v1.2 firmware does not answer the handshake**, even if motor commands still work.

**BLE connected and periodic telemetry received, no firmware reply:** This may be old firmware, serial receive wiring, or a dropped UART packet. The app reports a warning, not proof of a failed motor.

**No telemetry, but BLE writes work:** Some clones lack notifications on the selected characteristic. Without a return channel, this app cannot independently verify the Uno receives commands.

**Firmware handshake passes, buggy still stationary:** The problem is likely downstream of Arduino BLE UART: verify battery-to-VM, Arduino 5V-to-VCC, shared ground, D4 STBY, motor outputs, weak AA cells, motor solder joints. Upload `arduino/MotorTest/MotorTest.ino` to distinguish wiring/power faults from BLE control.

**Arduino doesn't appear as a COM port:** Check the USB data cable and Windows Device Manager. For a USB serial clone, check its CH340/CP210x driver as appropriate. Close Arduino IDE Serial Monitor when uploading. The diagnostics app only enumerates ports; it never opens or takes ownership of a port.

## Manual firmware handshake format

- Laptop sends `Q\n` to HM-10 BLE GATT UART, three attempts.
- Uno replies `H,13\r\n` on HM-10 TX/UART when matching firmware is loaded.
- Telemetry remains `T,<left>,<right>,<state>,<seq>\r\n` at most every approximately 1000 ms, after an RX quiet interval.
- The app still repeats the existing `M,left,right\n` or `K\n` motor/brake messages at approximately 120 ms.

The app expects **HM-10 at 9600 UART baud**. UART traffic may be broken into fragments by BLE notifications; the parser reconstructs complete lines and safely ignores unrecognizable bytes. The 1200 ms firmware motor-command watchdog remains enabled.

### Notes

- The BLE implementation uses Bleak's Windows WinRT backend and device objects from scans; no classic Bluetooth serial COM service is assumed.
- The diagnosis report remains local until you copy/save/share it. It can contain a selected Bluetooth device name/address or COM-port labels, so review it before posting publicly.
- Wireless firmware handshake support requires the matching updated Arduino sketch; there is no way for a pure Windows app to inject that feature into your already-programmed Uno remotely.

## Control Lab additions in v1.6.3

- **OFFLINE CONTROL CHECK:** click while disconnected or in Demo mode. Validates W/S/A/D motor computations, packet bounds, and motor-balance arithmetic, without communicating with the Arduino.
- **COMMAND LINK indicator:** shows last accepted GATT write age and duration. A link can accept a write even if the Arduino never receives the UART bytes.
- **EXPORT TRACE CSV:** exports the last 6,000 timestamped inputs, actual BLE write attempts accepted by Windows, Arduino PWM command telemetry, and safety events. Export after stopping movement; it is an aid for troubleshooting, not sensor data.
- **Motor Channel Lab:** upload `arduino/MotorTest/MotorTest.ino` (motor battery disconnected). Raise both wheels, connect USB, switch on motor battery, then send `T` in Serial Monitor at 9600 baud. The sketch individually tests left forward/reverse and right forward/reverse, then brakes. Restore the normal `BuggyController.ino` afterwards.


## v1.6.4 command-first firmware behavior

While a motor is commanded to move, Arduino HM-10 `SoftwareSerial` output
(telemetry and handshake) is intentionally paused to prevent half-duplex
transmissions from disrupting incoming drive packets. After releasing WASD
and waiting roughly 1 second, a fresh telemetry packet should arrive if
notifications are supported. A v1.6.4 packet includes a sixth field: the
**number of valid motor frames the Arduino accepted** (`RX CMD n`).

Never interpret stale telemetry *during driving* as a failed BLE connection
on this firmware. To investigate, export the flight recorder CSV after braking.
An increased accepted-frame count demonstrates that the Arduino parsed some
commands; it does not verify electrical B-channel voltage, wheel RPM, or a
physical motor stopping.

A watchdog trip now causes a latch until a deliberate brake command is
received; release the keys and re-press rather than expecting it to resume
automatically after a dropped Bluetooth stream. Escape brakes even when a
text field has focus; Space is reserved for normal typing in text fields.

The `OFFLINE LINK STRESS` button tests a deterministic simulator; it does
not connect to Bluetooth or test hardware.
