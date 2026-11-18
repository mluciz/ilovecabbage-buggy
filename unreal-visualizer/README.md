# BuggySensorViz — Unreal Engine 5 companion (isolated prototype)

This folder is an **additive prototype** on branch `feature/unreal-3d-sensor-visualizer-20261118`. It does not change the controller, motor commands, Arduino sketch, web dashboard, or existing downloads. Do not merge into the controller's active feature branch until tested.

## Start (Windows / Unreal Engine 5.4)
1. Install Unreal Engine 5.4 with C++ support and Visual Studio 2022 C++ game-development toolchain.
2. Right-click `BuggySensorViz.uproject` → Generate Visual Studio project files, build Development Editor / Win64, open the Unreal project.
3. Create a Basic level, drag **BuggyTelemetryActor** into the level (search Place Actors), position a camera looking down at world origin, and press Play.
4. Separately run `python tools/send_demo.py` (Python 3, standard library only). A blueprinted scene is not required; the actor spawns its own buggy cube and observation cubes. Stop the script to verify STALE indication.
5. When integrating real hardware, create a **read-only adapter** in the Python controller that emits JSON UDP to loopback port 48765; do not connect the Unreal app to Bluetooth or motor outputs directly. A real adapter is **not implemented yet**.

## Telemetry datagram (UTF-8 JSON, maximum 4096 bytes)
```json
{"schema":1,"source":"simulation","pose":{"x_m":0.2,"y_m":0.0,"yaw_deg":15},"imu":{"gyro_z_dps":2,"dt_s":0.05},"tof":{"valid":true,"distance_mm":620,"sensor_yaw_deg":0}}
```
- X/Y positions are metres in an **estimated local frame**. Unreal transforms to centimetres.
- `yaw_deg` is absolute estimated yaw. If `pose` is omitted, gyro Z is integrated using `dt_s`; this drifts.
- `tof.valid` must only be true for valid VL53L0X readings; `distance_mm` is a **one-dimensional range**, not object height, width or shape.
- `sensor_yaw_deg` is **known mounting/servo direction relative to the buggy**, not an inferred direction.
- Purple/grey cubes are geometric markers of range observations, **not verified obstacle volumes**. Multiple viewpoints plus calibrated pose/geometry are required before drawing reliable shapes.
- No position estimation from raw MPU-6500 acceleration is included; integrated acceleration drifts very quickly.
- Receiver binds only 127.0.0.1:48765 and never sends telemetry or motor commands.
- If three sensors means e.g. 2 VL53L0X + 1 MPU-6500, extend the packet to a `ranges[]` array after confirming the actual physical configuration. Two VL53L0Xs need separate XSHUT control/address assignment on the shared I2C bus.

## Hardware constraints / safety
- Determine the **specific breakout board's regulator and logic-level tolerance** from its marking/datasheet before connecting to a 5V Uno. MPU-6500 silicon is not inherently 5V-tolerant. Common MPU-6500 and VL53L0X modules differ in their onboard regulator/level shifting.
- I2C requires common ground, correct SDA/SCL, appropriate pull-ups at the correct voltage, and unique addresses. Extra resistors/capacitors do not automatically solve a logic-voltage mismatch.
- VL53L0X has limited field of view, occlusion, range and reflectance sensitivity; it cannot identify arbitrary obstacle shapes.
- The original right-wheel safety problem remains unresolved. Test with wheels raised, motor power under physical control, and no unattended driving.

## Non-goals of this prototype
No verified real-time hardware adapter, no SLAM, no reliable 3D reconstruction, no obstacle avoidance/autonomy, no UE packaged EXE, no physical validation. Unreal compilation has not been verified in this environment. The demo is a development starting point, not a safety system.
