# Start Here — Buggy Control Center v1.6.4

## If you don't have the buggy

1. Extract the complete ZIP.
2. Double-click `demo.bat` (requires Python on Windows). This never makes real BLE calls.
3. Click `OFFLINE CONTROL CHECK` and `OFFLINE LINK STRESS`. The latter
   simulates missed Bluetooth frames and demonstrates watchdog behavior;
   both are *software models*, not physical motor tests.
4. Try holding W, S, A, D, Space and Escape. Select `Precision drive` to try
   distinct lower manual gear values. This mode defaults OFF to preserve
   your older boost profile.
5. If you want to rerun the unit tests, double-click `offline_tests.bat`
   (installs pytest if missing).

## When you have the buggy

1. **Disconnect the motor battery before upload.** Connect Uno via USB.
2. Open `arduino/BuggyController/BuggyController.ino` and upload via Arduino IDE.
3. Confirm motor driver STBY has a 10 kΩ pulldown to GND in parallel with
   D4→STBY. The controller must not move by itself during upload/reset.
4. Raise the wheels, keep the motor battery switch within reach, connect BLE
   with Demo unchecked, and start with Precision Gear 1.
5. Test W for one second, release, test S for one second, then Space and Escape
   braking. The Arduino deliberately sends no telemetry *during* movement,
   but reports accepted-command counts after stopping.
6. If the right wheel moves unexpectedly or fails to brake, cut motor battery
   power. Upload `arduino/MotorTest/MotorTest.ino` with the motor battery
   disconnected, then use its serial-triggered left/right motor channel
   diagnostic with wheels raised; restore BuggyController afterward.

### What changed from v1.6.3

- Outbound firmware telemetry suppressed while driving, minimizing UART
  transmit/receive contention; after braking telemetry includes the
  accepted-command counter.
- Stalled BLE writes time out and trigger link shutdown.
- Watchdog brake requires deliberate re-arm before motion can resume.
- Optional Precision drive and offline link simulation.
- Escape global emergency-brake shortcut.

No real buggy was available during development; motor behavior is not
physically verified. Safety depends on working hardware and a battery switch.
