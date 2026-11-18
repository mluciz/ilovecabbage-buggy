# v1.8.3 updated HIGH-OUTPUT GEARS

The real BLE controller's distinct PWM drive levels are:

| Gear | Normal | Precision |
|---|---:|---:|
| 1 | 215 | 200 |
| 2 | 230 | 218 |
| 3 | 243 | 235 |
| 4 | 255 | 255 |

The prior version silently switched to Precision Gear 1 when the real Bluetooth link connected, using PWM 110, which could struggle against static friction. This version retains the conservative initial connection gear/precision state but uses PWM 200 instead of 110. Gears 2–4 also remain distinct. Precision is an optional modest reduction, not a low-torque crawl.

**Physical limitation:** Arduino analogWrite tops out at PWM 255. The PC app cannot make 255 faster; if Gear 4 is too weak on the floor, measure VM/GND loaded voltage and examine motor driver, battery current capability and gearbox drag. Right faster than left should be diagnosed physically before relying on balance compensation. Never bypass brake, overload, or overvoltage safeguards.

---

# Install CABBAGE Control Studio + Unreal Spatial Lab on Windows

This is a **test candidate**, not yet verified on the real motors or your HM-10 module.

## Normal installation — no terminal required

1. Download the **CABBAGE-Studio-v1.8.3-Windows-INSTALLER-FAST-GEARS** artifact from the latest successful Windows desktop installer build on [GitHub Actions](https://github.com/mluciz/ilovecabbage-buggy/actions/workflows/windows-candidate-build.yml). The build artifact downloads as a ZIP.
2. In Windows File Explorer, **Extract All**. Double-click **CabbageControlStudio-v1.8.3-Setup-FasterGears-CANDIDATE.exe** inside the extracted folder.
3. Follow the installation wizard. It installs **for your Windows user only**, without a Python installation or administrator account. Tick **Create a desktop shortcut** if desired.
4. Open **Start → Cabbage Control Studio → Cabbage Control Studio**. The application starts **DISCONNECTED** with the drive disarmed.
5. The connection row is **REAL BLE / HARDWARE**; it never connects to a buggy without your action. The simulator checkbox and Start Menu shortcut are no longer shown.
6. To uninstall later, use **Windows Settings → Apps → Installed apps → Cabbage Control Studio → Uninstall**.

You will not need to open Command Prompt, PowerShell, install pip packages, or run the `.bat` launchers for normal use.

## Open Unreal Spatial Lab from the installed app

1. Open **CABBAGE Control Studio** from the Start Menu or desktop. The app starts disconnected and brake-latched.
2. Click **SPATIAL LAB / 3D** on the left rail, choose **SYSTEM → OPEN SPATIAL LAB / 3D**, or press **F2**.
3. The app requests an emergency brake and **blocks launching while a real Bluetooth motor link is connected**.
4. The installer has copied the full `unreal-visualizer/BuggySensorViz.uproject` and C++ source inside the installed app folder. The launcher locates that project automatically. A compiled Spatial Lab executable you select is also supported.
5. The **SYSTEM → SELECT UNREAL EDITOR 5.4** button can link a custom Unreal installation: browse to `UnrealEditor.exe` in `UE_5.4\\Engine\\Binaries\\Win64`. The app remembers this path separately from the Spatial Lab project. If Unreal cannot be found when you press F2, the app offers the same file picker automatically. **Unreal Engine 5.4 and Visual Studio 2022 C++ build tools are separately required** to open or build the source project. The current candidate does **not** ship a compiled Unreal game, and your PC may ask to build its C++ modules when opening.
6. To explore the 3D scene, open the project in Unreal, then press **Play** in the Editor. Read the project guide at `%LOCALAPPDATA%\Programs\CabbageControlStudio\unreal-visualizer\README.md`.

The app installer does NOT automatically install Unreal Engine, install Visual Studio, update Arduino firmware, flash anything to your buggy, or transmit motor commands from Unreal. The Unreal visualization and sensor pipeline are still independent prototypes, not validated with physical sensors.

## Testing the REAL buggy: bench sequence, no simulator

The live app is intended for the existing HM-10 BLE + Arduino Uno + TB6612FNG buggy, not a replacement firmware or automatic sensor controller.

**Do NOT drive on the floor yet.** The reported HM-10 battery-power loss and right-wheel no-movement fault are physical blockers. The Windows CI has not validated motor drive or any wire.

1. **Disconnect motor power and inspect wiring.** Match physical Uno D4=STBY, D5=PWMA, D6=PWMB, D7/D8=AIN1/AIN2, D9/D10=BIN1/BIN2, and D2/D3 SoftwareSerial HM-10 lines against the current branch's documentation. Do not change wires while powered.
2. **Verify supply with a multimeter.** Measure the HM-10 breakout VCC to its GND under your intended battery supply, and compare USB power; confirm Uno regulated output and common ground. Do not assume an HM-10 is 5V tolerant merely because a breakout has side pins or an LED.
3. **Raise both drive wheels fully off the surface.** Have a hardware motor power disconnect accessible immediately.
4. Open the live desktop app. Ensure **REAL BLE / HARDWARE**, select the correct UART GATT characteristic (often FFE1 for compatible HM-10) and click **FIND DEVICES**; select the discovered module and click **CONNECT**. If the BLE module isn't powered, the software cannot discover it and motor testing must wait for the wiring fix.
5. In **System → Wheel Doctor**, do **SOURCE PIN AUDIT** (checks source declarations only). If main Arduino firmware supports **V,165** (newer firmware on this branch), allow the guarded single-wheel 450 ms probes only after satisfying both physical safety checks. Observe and record actual left/right forward/reverse and stopping. If no compatible handshake, the app refuses the pulse; the separately flashed `arduino/MotorTest/MotorTest.ino` is the alternative after disconnecting motor power before flashing.
6. If using the main drive view, select **Precision drive** and Gear 1, arm WASD deliberately, briefly hold a key with wheels suspended, then release and verify full braking. ESC and the physical battery switch must remain accessible. If the right wheel does not move, cut power and diagnose wiring/driver before proceeding.
7. Do not use automatic routes until physical braking, independent wheels, driver power and HM-10 command reception have been checked with your actual equipment.

**Unreal is independent.** The three VL53L0X ToF modules and MPU-6500 currently use a separate *sensor bench* sketch for read-only telemetry. The normal BLE drive firmware does not emit their ranges or IMU samples. The Unreal 3D map is not a safety controller or accurate real-time position estimator.

## Prefer not to install?

The same Actions run also has **CABBAGE-Studio-v1.8.3-PORTABLE-WITH-SPATIAL-LAB**. Extract its ZIP **with the entire `unreal-visualizer/` folder beside the EXE**, then open `CabbageControlStudio.exe` directly. It is a standalone Windows GUI with an embedded Python runtime. No installer or terminal is required. For permanent use, the installer is more convenient because it adds shortcuts and uninstall support.

## What the app does **not** do

- It does not install an Arduino sketch automatically, modify pins or fix your battery power circuit.
- It does not automatically connect to the HM-10, arm motors, run a route, or start at Windows login.
- It cannot determine actual wheel RPM, motor power voltage or braking from firmware PWM telemetry.
- It cannot confirm HM-10 3.3V module supply rating or whether the right motor driver output is physically wired correctly.

Before any real motor test, read the installed `Docs\WHEEL_DOCTOR_FIELD_GUIDE.md`, cut motor battery power before moving wires, and raise both wheels before a short bench test. Keep physical power cutoff immediately accessible.

## Notes

- Designed for **Windows 10/11 64-bit**.
- The EXE and installer are **unsigned experimental builds**. Windows may warn about an unrecognized publisher; verify the repository and downloaded filename before deciding whether to run them. They are not malware-scanned or hardware-certified by these CI tests.
- The installer **will not forcibly close a running buggy controller** to update it. Stop the motor and close CABBAGE Control Studio before installing a different candidate.
- Your harmless user tuning preferences are saved under your Windows profile, not in the app's install directory.
- If the app cannot start, it displays a message and writes a report under `%LOCALAPPDATA%\CabbageControlStudio\Logs\startup-error.txt`. Paste that report into a new bug report after removing any personally identifying paths.
- Downloadable CI artifacts have a limited retention period; if the artifact has expired, re-run the workflow from the GitHub Actions UI or build the current source using the developer scripts.

Source and issues: <https://github.com/mluciz/ilovecabbage-buggy>
