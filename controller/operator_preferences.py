"""Explicit, non-motion operator preferences for the Windows buggy controller.

Never persists arming, E-stop state, active routes, held keys, device address,
or any command that could move a real motor on startup.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

FIELDS = ("gear", "precision", "steering", "balance",
          "gatt_uuid", "measured_speed_cm_s", "wheel_spacing_cm")
DEFAULTS = {
    "gear": 2, "precision": False, "steering": 50, "balance": 0,
    "gatt_uuid": "FFE1", "measured_speed_cm_s": "22", "wheel_spacing_cm": "13",
}
_UUID = re.compile(r"(?i)([0-9a-f]{4}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\Z")


def config_path(base: str | os.PathLike | None = None) -> Path:
    if base is not None:
        directory = Path(base)
    elif os.getenv("BUGGY_CONFIG_DIR"):
        directory = Path(os.environ["BUGGY_CONFIG_DIR"])
    elif os.name == "nt":
        directory = Path(os.getenv("APPDATA") or Path.home()) / "CabbageControlStudio"
    else:
        directory = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config") / "cabbage-control-studio"
    return directory / "preferences.json"


def normalize(raw: dict | None) -> dict:
    data = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return data
    for key, low, high in (("gear", 1, 4), ("steering", 0, 100),
                           ("balance", -30, 30)):
        value = raw.get(key)
        if type(value) is int and low <= value <= high:
            data[key] = value
    if type(raw.get("precision")) is bool:
        data["precision"] = raw["precision"]
    uuid = raw.get("gatt_uuid")
    if isinstance(uuid, str) and _UUID.fullmatch(uuid.strip()):
        data["gatt_uuid"] = uuid.strip().upper()
    for key in ("measured_speed_cm_s", "wheel_spacing_cm"):
        try:
            v = float(raw.get(key))
        except (ValueError, TypeError, OverflowError):
            continue
        if 0.1 <= v <= 500 and v == v:
            data[key] = str(round(v, 3))
    return data


def load_preferences(base: str | os.PathLike | None = None) -> dict:
    path = config_path(base)
    try:
        if not path.is_file() or path.stat().st_size > 4096:
            return dict(DEFAULTS)
        return normalize(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeError):
        return dict(DEFAULTS)


def save_preferences(values: dict, base: str | os.PathLike | None = None) -> Path:
    """Crash-safe explicit save; no live control state is persisted."""
    safe = normalize(values)
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".tmp",
                dir=path.parent, delete=False) as out:
            temp = Path(out.name)
            json.dump({"version": 1, **safe}, out, indent=2, ensure_ascii=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        try:
            temp.chmod(0o600)
        except OSError:
            pass
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return path
