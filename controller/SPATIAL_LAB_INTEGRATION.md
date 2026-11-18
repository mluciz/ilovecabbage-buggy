# CABBAGE Control Studio v1.8 → Unreal Spatial Lab

## What was integrated

The v1.8 Windows cockpit gains **SPATIAL LAB / 3D** in its left quick-action rail and
**OPEN SPATIAL LAB / 3D** on the **SYSTEM** workspace. Press **F2** as a shortcut.
The new launcher's only job is to open the separate Unreal 5.4 visualizer. It
does not change BLE packets, drive steering, automatic route commands, motor
firmware or PWM timing.

The integration branch includes **both codebases**:
- `controller/`: v1.8 Control Studio GUI with launcher
- `unreal-visualizer/`: independent Unreal Spatial Lab v0.3 full project source

## What happens on click

1. Control Studio always requests its normal emergency brake and latches
   motor control off before launching.
2. If a **real BLE connection** is still active, launch is **blocked** with a
   warning to disconnect first. This prevents two foreground apps competing
   with drive-control key focus. A software stop is no substitute for cutting
   physical motor power.
3. If disconnected or simulator-only, the launcher searches for:
   - a previously selected local Spatial Lab target
   - a packaged `BuggySensorViz.exe` beside the studio
   - `unreal-visualizer/BuggySensorViz.uproject` beside the studio
   - conventional sidecar paths in the same extracted bundle
4. When it finds a compiled Spatial Lab EXE, it launches it directly.
   When it finds `.uproject`, it starts the project's **Unreal Engine 5.4
   Editor** using its explicit executable path.
5. If nothing is found, it opens a file picker for `BuggySensorViz.uproject`
   or a built `BuggySensorViz.exe`. A selection is saved in a local JSON
   file to make later launches one-click. No motors or Bluetooth secrets are saved.
6. It **never silently downloads, compiles, uploads or executes Arduino code**.
   Starting Unreal is non-blocking, so Control Studio stays responsive.

## Important practical distinction

The UE project is C++ source; **the v1.8 Windows candidate EXE is not itself
a compiled Unreal application**. With the new packaging workflow, the
Windows candidate artifact includes the complete `unreal-visualizer/` source
folder **next to** `Cabbage-Studio-v18-CANDIDATE.exe`, so the built studio
can locate `.uproject` automatically.

To use the project source, install Unreal Engine 5.4 and a compatible Visual
Studio C++ toolchain. For standalone operation without the Editor, build and
package Spatial Lab separately on Windows, then browse for its
`BuggySensorViz.exe`. The launcher remembers that path.

## End-to-end check (Windows)

1. Extract the **whole candidate artifact**, not just the EXE, preserving
   `unreal-visualizer/` beside `Cabbage-Studio-v18-CANDIDATE.exe`.
2. Open Control Studio using `demo.bat` or the candidate EXE.
3. Enter **SYSTEM**, click **OPEN SPATIAL LAB / 3D** (or press **F2**).
4. With Unreal 5.4 installed, the `.uproject` should open in the Editor and
   may need to compile its C++ modules. This Unreal runtime compilation has
   **not yet been verified** on a local Windows machine.
5. Press **Play** in Unreal. The independent Spatial Lab default demo scene
   should appear (3 ToF channels, MPU telemetry, obstacles and dashboard).
6. To test external data, switch Spatial Lab to EXTERNAL UDP, run
   `unreal-visualizer/launch_demo.bat`, and compare all 3 channel readings.
7. In Control Studio, connect a real BLE device only after explicitly
   closing or returning from Unreal, checking wiring and following the usual
   on-bench safety procedure. This launcher never connects Bluetooth itself.

## Tests and no-conflict policy

- Unit tests verify target selection, atomic path persistence, argument-list
  process launch (no shell), Windows/Unreal dependencies and motor-link blocking.
- CI includes the Spatial Lab Python tests, control studio regressions,
  candidate EXE packaging and presence of the Unreal source sidecar.
- This work lives on a **new child branch of the v1.8 candidate**, with a
  draft PR targeting the v1.8 branch. Neither the active v1.8 branch nor the
  Unreal development branch nor main was directly edited.
- Hardware and native Unreal C++ build are still unverified.
