#!/usr/bin/env python3
"""Zero-install local diagnostic preflight for the Cabbage Spatial Lab project.

CANNOT validate the physical voltage, sensor part numbers, motor wiring, or Unreal C++ build.
No serial ports are opened and no data is sent to the buggy.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import platform
import shutil
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@dataclass
class Check:
    name: str
    state: str
    detail: str
    suggested_action: str = ""

def check_udp_bind(port: int) -> Check:
    if not 0 < port < 65536:
        return Check(f"udp_{port}", "FAIL", "invalid port number")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", port))
        return Check(f"udp_{port}", "PASS", "available on loopback")
    except OSError as exc:
        return Check(f"udp_{port}", "INFO", f"already bound or blocked: {exc}",
                     "This can be expected if Unreal or a session capture is already running.")

def locate_ue() -> Check:
    if sys.platform != "win32":
        return Check("Unreal Engine 5.4", "INFO", "preflight running outside Windows",
                     "Use Unreal Engine 5.4 on Windows to compile and package.")
    roots = [Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files"))/"Epic Games"/"UE_5.4"]
    custom = os.environ.get("UE_ROOT")
    if custom: roots.insert(0, Path(custom))
    candidates = [root/"Engine"/"Binaries"/"Win64"/"UnrealEditor.exe" for root in roots]
    found = next((p for p in candidates if p.is_file()), None)
    if found:
        return Check("Unreal Engine 5.4", "PASS", str(found))
    return Check("Unreal Engine 5.4", "WARN", "not found at conventional path",
                 "Install UE 5.4, or point UE_ROOT to the Engine installation root.")

def inspect() -> list[Check]:
    checks: list[Check] = []
    checks.append(Check("Python", "PASS" if sys.version_info >= (3, 10) else "FAIL",
                        f"{platform.python_version()} on {platform.system()}",
                        "Use Python 3.10 or newer" if sys.version_info < (3, 10) else ""))
    project = ROOT/"BuggySensorViz.uproject"
    checks.append(Check("Unreal source", "PASS" if project.is_file() else "FAIL", str(project)))
    checks.append(locate_ue())
    checks.append(Check("pyserial", "PASS" if importlib.util.find_spec("serial") else "INFO",
                        "optional serial sensor-bench bridge only",
                        "py -3 -m pip install pyserial (only if connecting a dedicated sensor COM port)"))
    checks.append(check_udp_bind(48765))
    checks.append(check_udp_bind(48764))
    parent = ROOT/"tests"
    checks.append(Check("test suite", "PASS" if parent.is_dir() else "FAIL",
                        str(parent), "Run py -3 -m unittest discover -s tests -v"))
    # Explicitly avoid greenlighting unverified hardware.
    checks.append(Check("sensor electrical compatibility", "MANUAL",
                        "NOT CHECKED: verify module VIN/logic voltage, I2C level shifting, XSHUT pull-ups and power current"))
    checks.append(Check("motor isolation", "MANUAL",
                        "NOT CHECKED: disconnect motor battery before uploading any sensor bench sketch"))
    checks.append(Check("pose observability", "INFO",
                        "ToF + MPU-6500 alone cannot provide trustworthy absolute X/Y mapping"))
    return checks

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args()
    checks = inspect()
    if args.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        print("CABBAGE SPATIAL LAB / PRE-FLIGHT\n" + "="*39)
        for check in checks:
            print(f"[{check.state:6}] {check.name}: {check.detail}")
            if check.suggested_action:
                print("         next: " + check.suggested_action)
    sys.exit(2 if any(x.state == "FAIL" for x in checks) else 0)

if __name__ == "__main__":
    main()
