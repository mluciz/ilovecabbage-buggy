"""Pure driving and telemetry helpers. All PWM values are commands, not measured RPM."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MotorTelemetry:
    left_pwm: int
    right_pwm: int
    state: str
    sequence: int
    accepted_commands: int | None = None  # optional firmware v1.6.4 counter


_STATE = {'D': 'DRIVE', 'C': 'COAST', 'B': 'ACTIVE BRAKE', 'W': 'WATCHDOG BRAKE',
          'E': 'LATCHED EMERGENCY STOP'}
_TELEM_RE = re.compile(r'T,(-?\d{1,3}),(-?\d{1,3}),([DCBWE]),(\d{1,3})(?:,(\d{1,10}))?\Z')


def parse_telemetry(line: str) -> MotorTelemetry | None:
    """Parse bounded Arduino acknowledgements; reject malformed/random UART bytes."""
    match = _TELEM_RE.fullmatch(line.strip())
    if not match:
        return None
    left, right, state, sequence, command_count = match.groups()
    l, r = int(left), int(right)
    if not (-255 <= l <= 255 and -255 <= r <= 255):
        return None
    if command_count is not None and int(command_count) > 4294967295:
        return None
    return MotorTelemetry(l, r, _STATE[state], int(sequence),
                          int(command_count) if command_count is not None else None)


def manual_wheels(pressed: set[str], gear_pwm: int, sensitivity: int) -> tuple[int, int]:
    """0..100 sensitivity controls curve radius and pivot strength."""
    sensitivity = max(0, min(100, int(sensitivity)))
    speed = max(0, min(255, int(gear_pwm)))
    # An opposite-throttle combination must NEVER become a pivot simply
    # because A/D is also held. This can happen during keyboard rollover.
    if 'W' in pressed and 'S' in pressed:
        return 0, 0
    forward = int('W' in pressed) - int('S' in pressed)
    steer = int('D' in pressed) - int('A' in pressed)
    if not forward and not steer:
        return 0, 0
    if forward and not steer:
        return speed * forward, speed * forward
    if steer and not forward:
        power = round(speed * (0.30 + 0.70 * sensitivity / 100))
        return power * steer, -power * steer
    inside_ratio = 0.90 - 0.85 * sensitivity / 100
    inside = round(speed * inside_ratio)
    if steer > 0:
        return speed * forward, inside * forward
    return inside * forward, speed * forward


def approach_pwm(current: float, target: int, delta: float) -> float:
    """Smoothly approach a target PWM without jumping across direction reversals."""
    if delta < 0:
        raise ValueError('delta must be >= 0')
    if current < target:
        return min(float(target), current + delta)
    return max(float(target), current - delta)


def brake_rate(setting: int) -> float:
    """Return PWM reduction per second on key release: higher means sharper slowing."""
    return 260.0 + max(1, min(10, int(setting))) * 95.0


def balance_wheels(left: int, right: int, balance: int = 0) -> tuple[int, int]:
    """Optionally slow the stronger wheel, never boost the weaker above 255.

    Positive balance favors the right wheel (slows the left). Negative favors
    the left (slows the right). Applied only in manual mode; routes unchanged.
    """
    pct = max(-30, min(30, int(balance)))
    factor_l = (100 - max(0, pct)) / 100.0
    factor_r = (100 - max(0, -pct)) / 100.0
    return (max(-255, min(255, round(left * factor_l))),
            max(-255, min(255, round(right * factor_r))))
