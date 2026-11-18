"""CABBAGE Control Studio -> optional Unreal Spatial Lab launcher.

This module starts a separate local visualizer process. It does NOT connect to
Bluetooth, send UART packets, or modify Arduino firmware. Source projects need
Unreal Engine 5.4 and a working C++ toolchain installed on Windows.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Optional

class SpatialLabLaunchError(RuntimeError):
    pass

def settings_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "CabbageControlStudio" / "spatial_lab.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "cabbage-control-studio" / "spatial_lab.json"

def validate_target(candidate: str | Path) -> Path:
    path = Path(candidate).expanduser().resolve()
    if not path.is_file():
        raise SpatialLabLaunchError(f"Spatial Lab file not found:\n{path}")
    if path.suffix.lower() == ".uproject" and path.name.lower() != "buggysensorviz.uproject":
        raise SpatialLabLaunchError("Choose BuggySensorViz.uproject from the Spatial Lab project folder.")
    if path.suffix.lower() == ".exe" and "buggysensorviz" not in path.stem.lower() and "spatiallab" not in path.stem.lower():
        raise SpatialLabLaunchError("Choose the compiled BuggySensorViz / SpatialLab Windows executable.")
    if path.suffix.lower() not in (".uproject", ".exe"):
        raise SpatialLabLaunchError("Choose BuggySensorViz.uproject or a Spatial Lab .exe.")
    return path

def save_target(path: str | Path) -> Path:
    selected = validate_target(path)
    dst = settings_path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema": 1, "path": str(selected)}, indent=2), encoding="utf-8")
    os.replace(tmp, dst)
    return selected

def stored_target() -> Optional[Path]:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        if type(data) is dict and data.get("schema") == 1:
            return validate_target(data["path"])
    except (OSError, ValueError, TypeError, KeyError, SpatialLabLaunchError):
        pass
    return None

def candidate_paths() -> list[Path]:
    """Check source checkout and sidecar next to standalone PyInstaller EXE."""
    root = Path(__file__).resolve().parent
    exe_dir = Path(sys.executable).resolve().parent
    starts = [root.parent, root, exe_dir, exe_dir.parent]
    paths: list[Path] = []
    env = os.environ.get("CABBAGE_SPATIAL_LAB_PATH")
    if env:
        paths.append(Path(env))
    saved = stored_target()
    if saved:
        paths.append(saved)
    for start in starts:
        paths.extend((
            # Prefer a packaged Windows visualizer for true one-click use.
            start / "SpatialLab" / "BuggySensorViz.exe",
            start / "unreal-visualizer" / "Windows" / "BuggySensorViz.exe",
            start / "unreal-visualizer" / "Windows" / "BuggySensorViz" / "Binaries" / "Win64" / "BuggySensorViz-Win64-Shipping.exe",
            # Fallback to a source project (requires UE5.4 + VS toolchain).
            start / "unreal-visualizer" / "BuggySensorViz.uproject",
        ))
    # Unique by normalized path; never traverse arbitrary paths or execute a shell.
    result, seen = [], set()
    for candidate in paths:
        key = os.path.normcase(str(candidate.resolve(strict=False)))
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result

def discover_target() -> Optional[Path]:
    for candidate in candidate_paths():
        try:
            return validate_target(candidate)
        except SpatialLabLaunchError:
            continue
    return None

def unreal_editor_path() -> Optional[Path]:
    override = os.environ.get("UE_ROOT")
    roots = []
    if override:
        roots.append(Path(override))
    for var in ("PROGRAMFILES", "ProgramW6432"):
        if os.environ.get(var):
            roots.append(Path(os.environ[var]) / "Epic Games" / "UE_5.4")
    roots.append(Path("C:/Program Files/Epic Games/UE_5.4"))
    for root in roots:
        candidate = root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        if candidate.is_file():
            return candidate
    return None

def launch(target: str | Path, *, platform: Optional[str] = None,
           popen: Callable = subprocess.Popen, editor: Optional[Path] = None):
    """Launch an explicitly verified local file, never shell=True or a batch file.

    Returns the subprocess handle to let the caller report the PID.
    """
    if (platform or sys.platform) != "win32":
        raise SpatialLabLaunchError("Spatial Lab launch is supported on Windows only.")
    selected = validate_target(target)
    if selected.suffix.lower() == ".uproject":
        ue = editor if editor is not None else unreal_editor_path()
        if not ue or not Path(ue).is_file():
            raise SpatialLabLaunchError(
                "Unreal Engine 5.4 was not found. Install UE 5.4 with C++ tools, "
                "or select a previously packaged Spatial Lab .exe."
            )
        argv = [str(Path(ue).resolve()), str(selected)]
        workdir = selected.parent
    else:
        argv = [str(selected)]
        workdir = selected.parent
    try:
        return popen(argv, cwd=str(workdir), shell=False)
    except (OSError, ValueError) as exc:
        raise SpatialLabLaunchError(f"Could not open Spatial Lab: {exc}") from exc
