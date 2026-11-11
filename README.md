# ilovecabbage 🥬 — Buggy project

This is our shared repo for the **ilovecabbage team website**, downloadable buggy controller, Arduino firmware, and hardware reference documentation. Only one complete controller release is included, not the old version archives.

## Repository layout

- `index.html`, `styles.css`, `video.js`: the online cabbage-themed download website.
- `assets/`: **all 14** cabbage images from the shared Drive folder, all eight byte-for-byte segments of the physically rotated landscape video (with audio), and the video preview image.
- `downloads/`: one complete Windows Control Center ZIP and two Arduino sketches for direct downloading from the website.
- `controller/`: **editable** Python GUI, Bluetooth bridge, diagnostics, automatic route planner, Arduino firmware, offline tests, and latest included changelog.
- `hardware/`: original buggy project reference PDF.

## Quick start

1. **Website:** Open `index.html` locally or deploy this repository root as a static website. The currently hosted public version is https://buggy-team-hub.vercel.app.
2. **Windows:** Download/extract `downloads/Buggy_Control_Center_v1.6.4.zip`, install Python dependencies when needed, and launch `demo.bat` for offline simulation or `run.bat` to operate the buggy. Alternatively work directly with the Python files in `controller/`.
3. **Arduino:** Disconnect motor battery before uploading `controller/arduino/BuggyController/BuggyController.ino` via Arduino IDE (Arduino Uno). Use `controller/arduino/MotorTest/MotorTest.ino` for a separately triggered left/right motor diagnostic. Re-upload the normal sketch after testing.
4. **Tests:** `controller/offline_tests.bat` on Windows, or `python -m pytest controller/tests` where the required packages and display environment are available.

## Known hardware safety issue

The right wheel has previously rotated unexpectedly, responded poorly to reverse, and failed to brake as commanded. **No hardware correction is confirmed.** Do not drive unattended or on the floor until hardware is checked; test with both wheels raised and the motor battery's physical disconnect immediately accessible. GUI motor telemetry indicates *commanded PWM*, not measured actual wheel motion. Keep motor power disconnected during Arduino uploads. Verify STBY pulldown, ground, driver B-channel, and motor wiring independently.

## Release status

The most recent **complete source package actually available and verified in this workspace** is **v1.6.4**. A separate scheduled development task reported **v1.6.14**, but its complete source files were not recoverable in this session. **This repository does not claim to contain v1.6.14.** Do not mix the later-reported version's firmware with these files without verifying their compatibility.

Only the latest *available* controller build is tracked here, as requested. The hosted video is stored in eight byte-for-byte MP4 segments because a single 5 MB GitHub blob upload exceeded the connector limit. The website loads and joins these segments in `video.js`. To reconstruct the original standalone MP4, run `python tools/reassemble_video.py`; no video or audio bytes were changed.

## Collaborating

Clone the repository, create topic branches for changes, and include test evidence with commits or pull requests. Document physical motor-channel results separately from simulated testing.
