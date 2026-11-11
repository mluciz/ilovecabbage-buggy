"""Deterministic differential-drive mixing for signed-PWM Arduino protocol.

Positive values drive each *calibrated* wheel forward. Fix wheel polarity in
Arduino firmware (not here) after the independent motor-channel test.
"""
from __future__ import annotations

MIN_PWM = 0
MAX_PWM = 255
STEER_INNER_RATIO = 0.55


def mix(keys: set[str] | frozenset[str], speed: int,
        inner_ratio: float = STEER_INNER_RATIO) -> tuple[int, int]:
    if not 0 <= speed <= MAX_PWM:
        raise ValueError("speed must be between 0 and 255")
    if not 0 <= inner_ratio <= 1:
        raise ValueError("inner_ratio must be between 0 and 1")
    keys = {k.lower() for k in keys}
    if {"w", "s"} <= keys:
        return (0, 0)  # Conflicting controls must never unexpectedly pivot.
    direction = int("w" in keys) - int("s" in keys)
    steering = int("d" in keys) - int("a" in keys)
    if direction == 0:
        if steering < 0:
            return (-speed, speed)   # Pivot left.
        if steering > 0:
            return (speed, -speed)   # Pivot right.
        return (0, 0)
    if steering == 0:
        return (direction * speed, direction * speed)
    inner = round(speed * inner_ratio)
    if direction > 0:
        return (inner, speed) if steering < 0 else (speed, inner)
    # Reverse left/right steering follows the same physical yaw direction:
    # reverse left needs the LEFT wheel to reverse faster than RIGHT.
    return (-speed, -inner) if steering < 0 else (-inner, -speed)


def packet(left: int, right: int) -> bytes:
    if not all(type(n) is int and -255 <= n <= 255 for n in (left, right)):
        raise ValueError("motor powers must be integers in -255..255")
    return f"M,{left},{right}\n".encode("ascii")
