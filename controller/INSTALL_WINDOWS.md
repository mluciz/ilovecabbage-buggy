# Install CABBAGE Control Studio + Unreal Spatial Lab on Windows

This is a **test candidate**, not yet verified on the real motors or your HM-10 module.

## Normal installation — no terminal required

1. Download the **CABBAGE-Studio-v1.8.1-Windows-INSTALLER-SPATIAL-LAB** artifact from the latest successful Windows desktop installer build on [GitHub Actions](https://github.com/mluciz/ilovecabbage-buggy/actions/workflows/windows-candidate-build.yml). The build artifact downloads as a ZIP.
2. In Windows File Explorer, **Extract All**. Double-click **CabbageControlStudio-v1.8.1-Setup-SpatialLab-CANDIDATE.exe** inside the extracted folder.
3. Follow the installation wizard. It installs **for your Windows user only**, without a Python installation or administrator account. Tick **Create a desktop shortcut** if desired.
4. Open **Start → Cabbage Control Studio → Cabbage Control Studio**. The application starts **DISCONNECTED** with the drive disarmed.
5. To explore without motors, choose **Start → Cabbage Control Studio → Cabbage Studio — Demo (No Motors)**. This opens the same app in simulator mode with no BLE commands.
6. To uninstall later, use **Windows Settings → Apps → Installed apps → Cabbage Control Studio → Uninstall**.

You will not need to open Command Prompt, PowerShell, install pip packages, or run the `.bat` launchers for normal use.

## Open Unreal Spatial Lab from the installed app

1. Open **CABBAGE Control Studio** from the Start Menu or desktop. To avoid live motor movement, start in **Demo (No Motors)** or stay disconnected.
2. Click **SPATIAL LAB / 3D** on the left rail, choose **SYSTEM → OPEN SPATIAL LAB / 3D**, or press **F2**.
3. The app requests an emergency brake and **blocks launching while a real Bluetooth motor link is connected**.
4. The installer has copied the full `unreal-visualizer/BuggySensorViz.uproject` and C++ source inside the installed app folder. The launcher locates that project automatically. A compiled Spatial Lab executable you select is also supported.
5. **Unreal Engine 5.4 and Visual Studio 2022 C++ build tools are separately required** to open or build the source project. The current candidate does **not** ship a compiled Unreal game, and your PC may ask to build its C++ modules when opening.
6. To explore the 3D scene, open the project in Unreal, then press **Play** in the Editor. Read the project guide at `%LOCALAPPDATA%\Programs\CabbageControlStudio\unreal-visualizer\README.md`.

The app installer does NOT automatically install Unreal Engine, install Visual Studio, update Arduino firmware, flash anything to your buggy, or transmit motor commands from Unreal. The Unreal visualization and sensor pipeline are still independent prototypes, not validated with physical sensors.

## Prefer not to install?

The same Actions run also has **CABBAGE-Studio-v1.8.1-PORTABLE-WITH-SPATIAL-LAB**. Extract its ZIP **with the entire `unreal-visualizer/` folder beside the EXE**, then open `CabbageControlStudio.exe` directly. It is a standalone Windows GUI with an embedded Python runtime. No installer or terminal is required. For permanent use, the installer is more convenient because it adds shortcuts and uninstall support.

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
