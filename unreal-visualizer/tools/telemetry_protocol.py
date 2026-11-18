"""Validated, read-only JSON protocol for the Unreal Spatial Lab (schema 2).

Three *independent* VL53L0X readings are required in every datagram.
All units are explicit: mm, metres, degrees, seconds.
No commands can be represented by this protocol.
"""
from __future__ import annotations
import json
import math
from typing import Any

SCHEMA = 2
SENSORS = ("front", "left", "right")
MAX_BYTES = 4096
MAX_MM = 2000.0

class TelemetryError(ValueError):
    """Malformed or unsafe-to-visualize sensor packet."""

def number(value: Any, *, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TelemetryError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise TelemetryError(f"{name} outside [{low}, {high}]")
    return result

def validate_packet(data: Any) -> dict[str, Any]:
    if type(data) is not dict or type(data.get("schema")) is not int or data["schema"] != SCHEMA:
        raise TelemetryError("expected schema 2 object")
    readings = data.get("sensors")
    if not isinstance(readings, list) or len(readings) != 3:
        raise TelemetryError("exactly three sensor readings required")
    mapped = {}
    for row in readings:
        if not isinstance(row, dict):
            raise TelemetryError("sensor entry must be an object")
        sid = row.get("id")
        if sid not in SENSORS or sid in mapped:
            raise TelemetryError("unknown or duplicated sensor id")
        valid = row.get("valid")
        if type(valid) is not bool:
            raise TelemetryError("sensor valid field must be boolean")
        normalized = {"id": sid, "valid": valid}
        if valid:
            normalized["distance_mm"] = number(
                row.get("distance_mm"), name=f"{sid}.distance_mm", low=20.0, high=MAX_MM
            )
        mapped[sid] = normalized
    out = {
        "schema": SCHEMA,
        "source": str(data.get("source", "external"))[:32],
        "sensors": [mapped[sid] for sid in SENSORS],
    }
    pose = data.get("pose")
    if pose is not None:
        if not isinstance(pose, dict):
            raise TelemetryError("pose must be an object")
        out["pose"] = {
            "x_m": number(pose.get("x_m"), name="pose.x_m", low=-50, high=50),
            "y_m": number(pose.get("y_m"), name="pose.y_m", low=-50, high=50),
            "yaw_deg": number(pose.get("yaw_deg"), name="pose.yaw_deg", low=-36000, high=36000),
        }
    imu = data.get("imu")
    if imu is not None:
        if not isinstance(imu, dict):
            raise TelemetryError("imu must be an object")
        out["imu"] = {
            **{f"gyro_{axis}_dps": number(imu.get(f"gyro_{axis}_dps"), name=f"imu.gyro_{axis}_dps", low=-2000, high=2000) for axis in "xyz"},
            **{f"accel_{axis}_g": number(imu.get(f"accel_{axis}_g"), name=f"imu.accel_{axis}_g", low=-16, high=16) for axis in "xyz"},
            "dt_s": number(imu.get("dt_s"), name="imu.dt_s", low=0.000001, high=0.2),
        }
    return out

def decode_payload(payload: bytes | str) -> dict[str, Any]:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(raw) > MAX_BYTES:
        raise TelemetryError("datagram over 4096 bytes")
    try:
        return validate_packet(json.loads(raw))
    except (ValueError, TypeError, UnicodeError) as exc:
        if isinstance(exc, TelemetryError):
            raise
        raise TelemetryError("invalid JSON / encoding") from exc

def encode_payload(packet: dict[str, Any]) -> bytes:
    data = json.dumps(validate_packet(packet), allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_BYTES:
        raise TelemetryError("encoded datagram over 4096 bytes")
    return data
