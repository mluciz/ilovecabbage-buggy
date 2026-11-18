# Spatial Lab development log

## v0.3 — Isolated Unreal sensing & experience upgrade (2026-11-18)
- Added three demonstrator scenes (Arena, Corridor, Open Field) with independent obstacle arrays and scene reset.
- Added native editable front/left/right mounting angles, persisted in local `Saved/SpatialLab/mounts.json` (assumptions, not automatically calibrated).
- Added three per-channel range bars and closest-hit diagnostic threshold labels.
- Added accepted/rejected UDP packet counters and approximately recent 2-second packet rate.
- Added per-point CSV quality flags retained at capture time (synthetic vs externally supplied pose vs unlocated hit).
- Added non-destructive Unreal Editor Python asset-palette generator and optional material loading with plain-cube fallback.
- Added in-world heading marker and per-ray range labels.
- Added standard-library localhost UDP **session recorder, forwarder, replay and statistics**; no motor commands.
- Added one-click doctor / session-recording helpers, one-click Windows Unreal 5.4 build launcher, new test modules and Windows+Linux Python CI.
- No modifications to the existing motor controller, app release downloads or active wheel diagnostic branch.

## v0.2 — Base three-sensor prototype
- Three VL53L0X channels + MPU-6500 in schema-2 telemetry.
- Unreal C++ virtual buggy, sensor beams and short-lived observations; Python demonstration sender.
- Read-only serial bridge and isolated sensor-bench Arduino sketch.
- GameMode auto-spawn, camera controls, UMG dashboard.
- Observation export CSV.

## Limitations / do not misrepresent
Unreal C++ and editor runtime have **not been compiled, launched, visually inspected
or packaged in the current environment**. Python CI verifies protocol, session
and CLI code only. Real VL53L0X/MPU-6500 boards, current draw, I2C wiring,
motor fail-safe and physical mapping remain untested.
