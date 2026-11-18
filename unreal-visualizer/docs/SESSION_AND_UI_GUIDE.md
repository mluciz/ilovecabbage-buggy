# Spatial Lab field guide — three ToF channels + six-axis IMU

This is the operational companion to the Unreal Source prototype. **The current
branch is a source project, not a prebuilt EXE**, and physical sensor wiring /
Unreal C++ compilation still need actual Windows/engine validation.

## Setup in five steps

1. Run **`launch_doctor.bat`** (or `py -3 tools/doctor.py`). Verify Python
   version, Unreal project files, available UDP ports and optional pyserial.
   A report cannot measure logic levels or approve the physical wiring.
2. Open `BuggySensorViz.uproject` using **Unreal Engine 5.4** and a VS2022
   C++ desktop toolchain. If it reports missing modules, generate VS files
   from the .uproject and build `Development Editor | Win64`.
3. Press **Play** in the default Entry level. The GameMode builds the ground,
   five blocks, an estimated-geometry buggy and dashboard automatically.
4. Explore the left telemetry panel: range bars, closest-hit notice,
   packet count/rate, MPU-6500 accelerometer/gyro and mapping confidence label.
5. Try **NEXT TEST ENVIRONMENT** for Arena, Corridor and Open Field. The UI
   prevents switching the scene when external hardware telemetry is selected.

## Native Unreal interface

- **Internal Demo / External UDP**: default is wholly synthetic. Switching
  clears old map observations to avoid mixing real and simulated data.
- **Camera**: `Q/E` orbit, `R/T` tilt, `V` overhead, `F` recenter,
  `Home` reset, mouse wheel zoom. Click the 3D viewport for keyboard focus.
- **Range bars**: a fuller bar means **closer valid hit** (not signal quality).
  Invalid readings show no distance; do not infer a clear path.
- **Proximity warning**: 250 mm close, 550 mm near. This is a *visual*
  indication, not an automatic braking or collision-avoidance controller.
- **Mount angles**: front, left, right bearings in degrees. Once changed, values are saved to local `Saved/SpatialLab/mounts.json` and loaded at the next start. Profiles are deliberately marked `physically_verified=false` until hardware measurements are established. The default
  0 / +55 / -55 arrangement is **assumed**. Measure the three mounts and set
  those actual angles. Applying clears old points because map rays change.
- **Point CSV export**: `Saved/SpatialLab/observations_UTC.csv` with
  per-point quality flags. A CSV of hit endpoints is **not** SLAM.

## Repeat an experiment without driving the buggy

A capture proxy on UDP 48764 receives sensor frames and forwards valid packets
to the Unreal receiver on 48765, recording validated JSONL.

In the Unreal app, select **EXTERNAL UDP**, then double-click
`record_session.bat` or from the project folder:

```powershell
py -3 tools/session_tool.py capture --out sessions/trial_001.jsonl --duration 30
```

Feed one of these sources to **port 48764** instead of 48765:

```powershell
py -3 tools/demo_sender.py --port 48764 --scenario sensor-dropout --duration 30
```

Or with a separately flashed **sensor-only** Arduino and the serial monitor
closed:

```powershell
py -3 tools/serial_bridge.py --serial-port COM8 --baud 115200 --port 48764
```

View the session statistics, including per-channel hit counts and dropout gaps:

```powershell
py -3 tools/session_tool.py inspect sessions/trial_001.jsonl
```

Then replay to Unreal at half, real or double time:

```powershell
py -3 tools/session_tool.py replay sessions/trial_001.jsonl --speed 0.5
py -3 tools/session_tool.py replay sessions/trial_001.jsonl --speed 1
py -3 tools/session_tool.py replay sessions/trial_001.jsonl --speed 2
```

`replay` validates the complete recording before forwarding anything. It
sends sensor JSON only to localhost; it **never controls a motor**. Avoid
running external demo_sender, replay and real sensor bridge to the same
receive port simultaneously.

## Optional colour palette

Default scene uses Unreal's engine cube materials. For a more legible
coloured appearance, enable the built-in **Python Editor Script Plugin**
in Unreal's plugins settings, restart the Unreal Editor, and run this
in the Unreal Editor Python console:

```python
exec(open(r"C:\FULL\PATH\TO\unreal-visualizer\tools\create_materials_unreal.py").read())
```

The script creates **seven separate materials** in
`Content/SpatialLab/Materials`, skipping existing assets. The C++ game
loads them when present and falls back to engine materials otherwise. The
script hasn't been executed/verified in an Unreal 5.4 Editor in this workspace.
Generated `.uasset` files remain local until committed deliberately.

## After a sensor connection failure

- Run `launch_doctor.bat`; port 48765 occupied can be **normal** when Unreal
  is already running. Port 48764 is a separate capture proxy listener.
- If all sensors show no hit in the **Open Field**, that is expected.
- If external mode remains `NO RECENT DATA`, check that the sender emits
  **schema 2**, that all three IDs are present exactly once, and that the
  output port is 48765 (direct) or 48764 (recording proxy).
- If all three appear under one physical address, they were not individually
  released from XSHUT and readdressed. Power-cycle and follow the bench sketch.
- If the MPU-6500 is missing, check the module I2C address, supply,
  I2C voltage compatibility and physical soldering without motor power.
- For unreliable voltage on the Uno's 3.3-V pin, independently verify
  regulated supply rails, shared ground, current capacity and breakout
  requirements **before** connecting modules.

## Hardware safety boundary

No wheel-encoder odometry exists in the current motor firmware, and this
project cannot reconstruct a real-world 3D obstacle shape from three
static one-dimensional range measurements. The floor + obstacle volumes
are **synthetic demo ground truth**. Live mode points are range endpoints
whose world coordinates are only meaningful if external pose and mounting
calibration are credible. Never use this app as collision protection.
