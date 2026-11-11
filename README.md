# ilovecabbage 🥬 — Buggy Project

This repository is the team's **single working copy** for the current available website and buggy source. It includes:

- **Website**: `index.html`, `styles.css`, `video.js`, all 14 cabbage photos, and the landscape team video in `assets/`.
- **Windows Control Center**: editable Python GUI, BLE bridge, route planning, diagnostics, flight recorder and regression tests in `controller/`.
- **Arduino Uno**: matching `BuggyController.ino` and independent `MotorTest.ino` inside `controller/arduino/` and convenient downloads under `downloads/`.
- **Project reference**: the hardware brief in `hardware/`, with wiring guidance and original project documentation.

## Quick start

1. Open the hosted website: https://buggy-team-hub.vercel.app
2. Download `downloads/Buggy_Control_Center_v1.6.4.zip`, extract it, and launch `demo.bat` to test without hardware; use `run.bat` for the real Windows controller.
3. To update Arduino firmware, disconnect the motor battery before uploading `controller/arduino/BuggyController/BuggyController.ino` to an Arduino Uno via Arduino IDE.
4. Test the right wheel and braking with the wheels lifted, the physical battery switch accessible, and the independent `MotorTest.ino` sketch when appropriate.

**Hardware safety:** Previous tests found that the right wheel sometimes moved unexpectedly and ignored reverse/braking. Software feedback indicates commanded PWM, **not actual wheel rotation**. Do not perform unsupervised powered driving until both channels and physical emergency-stop behavior are verified.

## Release provenance

The most recent **complete source package available to verify and publish** here is **Buggy Control Center v1.6.4**. A completed scheduled development task reported a later **v1.6.14**, but the final source ZIP is *not accessible* from this repository-creation session. This repo does **not** claim to contain v1.6.14. Please replace the controller source and downloads with the newer release only after its actual files are recovered and verified; do not mix firmware and GUI versions.

Only the latest **available** release is tracked, not old release ZIPs. The website is static, so the repo root can be deployed directly to Vercel. The full website video is a regular MP4; no chunk-loading is needed.

## Collaboration

Make small commits for changes, document reproducible tests and record what happens on the physical buggy. To work locally, clone this repository; Python dependencies are listed in `controller/requirements.txt`. `controller/offline_tests.bat` runs software tests on Windows.
