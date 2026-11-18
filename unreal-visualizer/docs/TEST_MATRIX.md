# Spatial Lab QA checklist

## Automated, standard-library only
`python -m unittest discover -s tests -v`

Tests cover: exactly three unique IDs, unknown/duplicate IDs, bad booleans,
NaN and infinity rejection, impossible ranges, missing pose data,
six-axis IMU validation, max packet size, JSON round trip, demo
scenarios and 2D ray/box intersections.

## Unreal Editor manual smoke test (not yet run in this environment)
1. Build in Unreal Engine 5.4 / VS2022. Project opens without need to add an actor manually.
2. Press Play on the Engine Entry level. Expect floor grid, cube buggy, five simulated boxes,
   labelled cyan/lime/orange beams and left-side sidebar.
3. Wait 3 seconds. Three channels should display distances when a ray hits; NO VALID HIT is normal if there is no intersecting target.
4. Click PAUSE/RESUME. Pose and point count should freeze and resume.
5. Click CLEAR. Point count should become zero and increase again while demo is running.
6. Toggle ray overlays, simulated box geometry and camera.
7. Use Q/E orbit, R/T pitch, mouse-wheel zoom, V top-down, F focus and HOME reset.
8. Click SWITCH TO LIVE STREAM. Status must be NO RECENT DATA until an external sender begins. No demo boxes should be shown in live mode.
9. In a terminal: `python tools/demo_sender.py --scenario arena --duration 20`.
   Expect all three IDs and packet acceptance increasing. Stop sender; after 1.5 seconds range display should become stale.
10. Repeat with `--scenario sensor-dropout`: left sensor must show NO VALID HIT during simulated outages.
11. Verify invalid UDP datagrams are dropped and do not move the buggy.
12. Verify task never writes any motor outputs or Bluetooth commands.

## Hardware bench test (NOT completed)
- Measure sensor voltage and XSHUT logic levels before connection to Uno.
- Confirm each unique I2C address after startup and after power cycle.
- Compare VL53L0X distances against a ruler at several positions and surface reflectances.
- Confirm IMU yaw sign and each gyro/accelerometer axis physically.
- Confirm left/right mounting orientation and coordinates against the real buggy.
- Keep motor battery physically isolated throughout sensor bench testing.
- Verify real hardware source emits valid full schema-2 telemetry lines.

## No verified claims
C++ Unreal build, packaging, visual UI, real sensor board, power integrity and physical mapping
are not validated until run on a machine with UE 5.4 and the actual modules.
