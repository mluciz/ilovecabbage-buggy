# Buggy wheel / Bluetooth control audit — 2026-11-11

## Source provenance and scope

The GitHub repository's \`main\` branch contained **only a README** when the audit began. The v1.6.4 Arduino sketch and independent \`MotorTest.ino\` were recovered from the connected Google Drive. The original v1.6.4 Windows Python GUI source is **not currently present in GitHub or accessible as an individual source file**; a historical ZIP exists in a Vercel deployment but was not available for full code inspection in this session. The new \`controller/app.py\` is a deliberately small, auditable BLE control alternative — **not** a claim to have fixed or audited every feature of the missing historical GUI.

Firmware version tag: \`v1.6.5-safety\`. The handshake \`H,13\` and existing \`M,<left>,<right>\\n\` protocol remain compatible with older applications that send framed signed PWM; extra \`X\` (latching E-stop) and \`U\` (explicit unlock) commands are opt-in. The app sends K and X on initial connection, and U followed by M,0,0 only on an explicit ARM action.

## Issues identified from v1.6.4 source and mitigations

1. **Interleaved USB/BLE parser data:** The old sketch shared a single \`packet\`, \`packetPos\` and \`receivingPacket\` across both interfaces. A partial BLE frame and USB debug message could corrupt each other. **Fixed:** independent receive state per port.
2. **Sudden polarity reversal:** An immediate forward-to-reverse command changed direction without an interlock. **Fixed:** brake both motor channels for 70 ms before applying reversal; new drive requests may update the pending target, and any STOP cancels it without blocking the input loop.
3. **Unlatching emergency stop:** The old K command immediately cleared watchdog lockout, so later queued frames could resume motion. **Improved:** K brakes and needs an explicit zero packet to release the ordinary lockout; X latches an E-stop that is released only by U and then a zero packet. This is not a substitute for cutting motor battery power.
4. **Asymmetric motor updates:** The old sketch applied left PWM/direction and then right PWM/direction in sequence. **Improved:** both PWM enables are shut off before direction pins change, then both channels are enabled.
5. **Turning decisions in the app:** The old GUI source could not be verified. The new \`motion.mix()\` provides deterministic straight, pivot and gradual arc turns, with conflict handling, PWM bounds, and unit tests.
6. **UI or wireless failure:** Existing 1,200 ms firmware watchdog retained. New app independently stops and latches E-stop if its Tkinter event loop stops issuing heartbeats for 650 ms, and stops on focus loss or disconnect. BLE write failures disable motion. A hardware-level motor cut-off is still required.
7. **Physical right wheel problem:** Previous reports say the right wheel sometimes moves unexpectedly and does not brake/reverse reliably. **Not fixed by software until the actual cause is known.** Possible causes include wiring/pin mismatch, motor-driver B channel damage, inadequate motor supply/ground, or motor wiring/polarity. The firmware has *no wheel encoders*, so displayed commanded PWM cannot prove rotation.

## Wiring assumptions

Arduino Uno + TB6612FNG + HM-10:
- D4=STBY, D5=PWMA, D6=PWMB, D7=AIN1, D8=AIN2, D9=BIN1, D10=BIN2
- D2 Arduino RX <- HM-10 TX; D3 Arduino TX -> HM-10 RX **through 3.3 V level conversion**.
- All controller/motor driver grounds common; motor VM powered separately per driver spec. Motor VM MUST have an accessible physical cut-off. Never power motors through Arduino 5 V pin.
- Left motor on A channel and right motor on B channel assumed.
- \`LEFT_MOTOR_POLARITY\` and \`RIGHT_MOTOR_POLARITY\` both default to \`+1\` as in the recovered source: **these may not match your mirrored physical wheel mounting**. Change to \`-1\` on the misdirected side after testing. The host mixer assumes positive signed PWM means physical forward on both sides.

## Safe test procedure — do not skip

1. Disconnect motor battery; inspect wiring and loose connections, especially right channel B; verify physical motor power switch.
2. Upload **MotorTest** via Arduino IDE (board Arduino Uno). Raise wheels off the floor. Reconnect motor power. Open Serial Monitor at **9600** and send \`T\`. Each of six steps is **650 ms**, with **600 ms** braking pauses. Send \`X\`/ \`S\` to abort (or use the physical switch if something moves incorrectly).
3. Record actual observations for: left forward, left reverse, right forward, right reverse, both forward, both reverse. In particular: does **right reverse** work? Does right stop in each gap? Any spontaneous wheel motion? If **any** fails, **do not attempt ground driving**. Investigate right motor wiring / TB6612FNG B outputs / STBY and supply. The software cannot correct a stuck output transistor.
4. MotorTest raw '+' is driver-channel direction, not necessarily physical forward. Determine whether left or right polarity must be inverted for the normal firmware.
5. Switch motor battery OFF before uploading **BuggyController**. Change polarities if necessary. Reconnect with wheels raised.
6. Run \`controller/install.bat\` once, then \`controller/run.bat\` from the repository (Python required). Scan for your **HM-10 / HMSoft** BLE device and connect. Connection starts latched/braked. With wheels raised, click ARM, start at low speed, test W, S, A, D, W+A, W+D, S+A and S+D; release every key and verify both wheels stop.
7. During a low-speed run, use E-STOP. Verify new motion does not restart without ARM. Temporarily kill BLE / app and confirm watchdog brake. **Do not** touch the wheels while powered.
8. Only after every wheel and stop test passes may you consider a slow ground test in a clear controlled area.

## Automated checks

- \`python -m unittest discover -s tests -v\` exercises the Python drive mixer.
- The native C++ harness compiles the *actual Arduino sketch* against fake pin I/O and tests parser interleaving, malformed frames, turnaround brake delay, stop during delay, watchdog and latched E-stop.
- GitHub Actions additionally compiles the two Arduino sketches for \`arduino:avr:uno\`.
- **Limits:** All simulations test requested pin states, not real motors, current, wheel encoders, BLE radio timing, or right-channel hardware health.

## Known remaining limitations

- No physical measurement of wheel speed; PWM does not guarantee equal rotations, straightness, traction or direction.
- No encoders/IMU: cannot compensate wheel mismatch or accurately drive set distances/angles.
- SoftwareSerial on Uno is half-duplex. Telemetry is suppressed while moving by default and can still collide with incoming BLE frames while stopped. The watchdog is a last resort; a physical power cut-off remains essential.
- Legacy software sending K then M,0,0 may clear the ordinary brake lockout. Use the new app's X latch for a stronger software emergency stop. Do not assume compatibility with every older third-party controller.
- Historical GUI and its route planning / flight recorder were **not audited**. A complete source archive is needed before claiming that.
