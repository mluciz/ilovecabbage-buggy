# ilovecabbage Spatial Lab — Unreal Engine 5.4 3D visualizer

An **isolated companion project** for the buggy's **three VL53L0X range sensors + one MPU-6500 IMU**. It does not modify the existing buggy website, Bluetooth controller, releases or Arduino drive firmware. Every project source file lives inside `unreal-visualizer/` on the dedicated feature branch.

**Status:** Source-built prototype; *not* UE-compiled, packaged or hardware-tested by this environment. It contains an internally generated 3D scene and an interactive C++ UMG dashboard. It is intended to become a polished app, not an autonomous navigation system.

## Start the Unreal app — Windows

Requirements: Unreal Engine **5.4** installed from Epic Games Launcher; Visual Studio **2022** with Desktop C++ and Game Development with C++ components (Windows SDK / UE toolchain); a Windows PC capable of UE5.

1. Open `BuggySensorViz.uproject`. If prompted to generate or rebuild C++ project modules, choose Yes. If the build fails, use right-click `BuggySensorViz.uproject` → Generate Visual Studio project files; open the solution; build `Development Editor | Win64`.
2. Open the default `Entry` map; press **Play**. No handcrafted `.umap` is required: the game mode spawns a buggy, ground grid, five demonstration objects, camera and dashboard.
3. Default is **INTERNAL SIMULATION**. Watch the front/left/right distance readings and white/green/blue/orange observation markers.
4. Use the in-app buttons to pause, clear map points, hide rays, hide demo geometry, change camera, focus, or switch to external UDP.
5. Controls: `Q/E` orbit; `R/T` camera tilt; `mouse wheel` zoom; `V` top view; `F` focus; `Home` camera reset. Click the 3D viewport first if keyboard focus remains in the UI.

### External test sender (no hardware)

Start the Unreal scene, press **SWITCH TO LIVE STREAM**, then double-click `launch_demo.bat` or run:

```powershell
py -3 tools\demo_sender.py --scenario arena --duration 30
py -3 tools\demo_sender.py --scenario sensor-dropout --duration 30
py -3 tools\demo_sender.py --scenario turning --duration 30
```

Each packet has three independent VL53L0X channels and six MPU-6500 measurement fields. Python demo tools require only the standard library. All UDP is send-only to **127.0.0.1:48765**. The Unreal process is **receive-only** and has no motor command API.

### Automated Python tests

```powershell
py -3 -m unittest discover -s tests -v
```

Or double-click `run_tests.bat`. See [QA matrix](docs/TEST_MATRIX.md).

## UDP schema 2

One UTF-8 JSON object per datagram, maximum **4096 bytes**, e.g.:

```json
{
  "schema": 2,
  "source": "simulation",
  "sensors": [
    {"id": "front", "valid": true, "distance_mm": 600},
    {"id": "left", "valid": true, "distance_mm": 810},
    {"id": "right", "valid": false}
  ],
  "imu": {
    "gyro_x_dps": 0, "gyro_y_dps": 0, "gyro_z_dps": 1.2,
    "accel_x_g": 0, "accel_y_g": 0, "accel_z_g": 1,
    "dt_s": 0.08
  },
  "pose": {"x_m": 0.1, "y_m": -0.03, "yaw_deg": 5}
}
```

- `sensors`: exactly three, one each `front`, `left`, `right`. `valid=false` indicates NO VALID HIT, *not* zero distance. Valid range in this prototype is 20–2000 mm.
- `pose` is **optional**. It must be supplied by a separate externally verified pose estimator; it does **not** come from three VL53L0X range readings or an MPU alone. If absent, the local estimated X/Y stays fixed and gyro Z alone advances yaw (which drifts).
- `imu` is optional, but if supplied it must include **three gyroscope components** in deg/s, **three accelerometer components** in g, and a positive `dt_s` ≤0.2. Pitch and roll are a basic complementary visualization estimate, not a calibrated orientation measurement.
- Default simulated sensor angles are front 0°, left +55°, right −55°. These are **unverified mounting assumptions** that can be changed in `ABuggyTelemetryActor` properties.
- In the DEMO scene, solid boxes are known **synthetic obstacles**. In external mode, the dots show measured ray endpoints, not reliable reconstructed 3D obstacle bodies. Sensor field-of-view lines are suggestive, not dense scanning.
- A stale external stream (>1.5 s) invalidates the displayed ranges. Switching modes clears old observations.

## Physical sensor demonstration (optional, separated from driving firmware)

After following the [pin/voltage audit](docs/HARDWARE_AND_PIN_AUDIT.md), the separate **sensor-only bench** sketch is located at `firmware/SensorBench3ToF/SensorBench3ToF.ino`. It uses the Pololu `VL53L0X` Arduino library, independent XSHUT control on *bench-only* A0/A1/A2 and optional raw MPU-6500 I2C registers. It prints sensor-only schema-2 JSON on USB serial. It neither starts nor controls motors.

For a **dedicated sensor bench COM port**, close Arduino Serial Monitor and run:

```powershell
py -3 -m pip install pyserial
py -3 tools\serial_bridge.py --serial-port COM8 --baud 115200
```

Replace COM8 with the actual separate sensor port. This cannot silently share the active motor-controller serial session, and it does not magically add sensing to the unchanged Arduino motor firmware. A safe fully integrated controller requires separate work, pin verification, and watchdog timing review.

## Source directories

- `Source/`: Unreal C++ game mode, native dashboard, 3D buggy + floor + synthetic boxes, live ToF ray visualizer, limited observation history, orbit/top camera
- `Config/`: Engine game mode, startup map, input controls
- `tools/`: strict protocol, external three-channel demo, read-only serial bridge
- `tests/`: standard-library protocol and geometry unit tests
- `firmware/`: **bench-only sensor sketch**, never touched the regular buggy sketch
- `docs/`: pin audit and QA matrix

## Known limitations

- Unreal C++ compilation, packaging, visual output and actual sensor integration have NOT been verified in this runtime. A source project is **not** a ready-to-install Windows EXE.
- The original buggy has unresolved right-wheel drive/braking problems. Keep motor battery **disconnected** during sensor bench testing.
- No wheel encoders / independent odometry / calibrated IMU fusion / loop closure / SLAM / autonomous navigation exist yet. Position, object shapes and absolute heading cannot be made trustworthy from these four sensors alone.
- VL53L0X modules' power, I2C and XSHUT voltage requirements differ by breakout board. Verify voltage domains and pull-ups before wiring to 5-V Arduino Uno.
