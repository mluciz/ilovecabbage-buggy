# Build Spatial Lab safely on Windows

**This repository contains editable Unreal C++ source, not an already tested EXE.**

## Requirements

- Windows 10/11 x64; Epic Games Launcher with Unreal Engine **5.4** installed.
- Visual Studio 2022 and the C++ Game Development workload, Windows SDK and
  MSVC toolchain configured for Unreal 5.4.
- Python 3.10+ to run optional simulation and diagnostic tools.

## One-click local build

1. Clone or download the **feature/unreal-3d-sensor-visualizer-20261118** branch.
2. Open the `unreal-visualizer` folder.
3. Run `launch_doctor.bat` to check your Python and file setup.
4. Run **`build_and_open_unreal.bat`**. It uses the installed `UE_5.4`
   directory by default. Set the `UE_ROOT` environment variable if your
   installation lives elsewhere.
5. Inspect the compiler's log. If the build succeeds, the script opens
   Unreal Editor with the project. Press Play to enter the synthetic lab.
6. Optionally generate the seven coloured materials from the Unreal
   Python script (documented in [UI guide](SESSION_AND_UI_GUIDE.md)).

## Manual build fallback

Right-click the `.uproject` and choose Generate Visual Studio project files;
open generated solution; select **Development Editor / Win64**, build;
launch `BuggySensorViz.uproject`.

## Packaging an EXE (after source builds and Editor testing)

In Unreal Editor: **Platforms > Windows > Package Project** (menu layout may
vary with UE version), choose a new output directory, and inspect the
Packaging/Output Log. Package only **after** you have tested the scene,
camera, UI, UDP receiver and optional materials in Editor. No prebuilt EXE
is claimed in this repository.

## No-conflict guarantee boundary

- No changes to `controller/`, `downloads/` or Arduino motor firmware.
- Build script operates only on this local Unreal project and generated
  Unreal intermediates.
- **Do not merge** this draft PR into main until Windows UE build and real
  bench wiring have been reviewed.
- Three-ToF packets never contain a motor command.
