"""Ideal, open-loop path planning for a two-wheel differential-drive buggy.

All geometric units are centimetres / seconds. This is NOT odometry: real-world
accuracy requires wheel encoders, calibration, and ideally heading feedback.
"""
from dataclasses import dataclass
from math import cos, sin, radians, degrees, pi, hypot

GEARS = {1: 220, 2: 255, 3: 255, 4: 255}  # doubled from original; PWM capped at 255


@dataclass(frozen=True)
class Segment:
    label: str
    left: int
    right: int
    duration: float


def _positive(value, name, upper=1000.0):
    value = float(value)
    if not (0.0 < value <= upper):
        raise ValueError(f"{name} must be between 0 and {upper:g}.")
    return value


def _angle(value):
    value = _positive(value, "Angle", 3600)
    return value


def _pwm(value):
    return max(-255, min(255, int(round(value))))


class Planner:
    def __init__(self, full_speed_cm_s=22.0, wheelbase_cm=13.0, gear=2):
        self.max_speed = _positive(full_speed_cm_s, "Gear 4 measured speed", 200)
        self.wheelbase = _positive(wheelbase_cm, "Wheel spacing", 100)
        self.gear = int(gear)
        if self.gear not in GEARS:
            raise ValueError("Gear must be between 1 and 4.")
        self.pwm = GEARS[self.gear]
        self.speed = self.max_speed * self.pwm / 255.0
        self.parts = []

    def _add(self, label, left, right, seconds):
        if not (0 < seconds < 900):
            raise ValueError(f"{label} has an invalid duration. Reduce the route dimensions.")
        self.parts.append(Segment(label, _pwm(left), _pwm(right), seconds))
        if len(self.parts) > 200 or sum(p.duration for p in self.parts) > 900:
            raise ValueError("Route exceeds the safety limit (200 steps or 15 minutes).")

    def straight(self, cm, reverse=False):
        cm = _positive(cm, "Straight length")
        direction = -1 if reverse else 1
        self._add(("Reverse" if reverse else "Forward") + f" {cm:g} cm",
                  direction * self.pwm, direction * self.pwm, cm / self.speed)

    def pivot(self, way, angle_degrees):
        angle_degrees = _angle(angle_degrees)
        if way not in ("L", "R"):
            raise ValueError("Turn direction must be L or R.")
        # Opposite wheel speeds -> angular rate = 2 * v / wheel spacing.
        seconds = radians(angle_degrees) * self.wheelbase / (2 * self.speed)
        left, right = (-self.pwm, self.pwm) if way == "L" else (self.pwm, -self.pwm)
        self._add(f"Turn {'left' if way == 'L' else 'right'} {angle_degrees:g}°",
                  left, right, seconds)

    def arc(self, way, radius_cm, angle_degrees):
        radius_cm = _positive(radius_cm, "Radius")
        angle_degrees = _angle(angle_degrees)
        if way not in ("L", "R"):
            raise ValueError("Arc direction must be L or R.")
        # Outer wheel at selected gear; inside wheel scales by radius ratio.
        # If radius < half wheel spacing, inside wheel reverses, as required.
        ratio = (radius_cm - self.wheelbase / 2) / (radius_cm + self.wheelbase / 2)
        inner = _pwm(self.pwm * ratio)
        left, right = (inner, self.pwm) if way == "L" else (self.pwm, inner)
        seconds = radians(angle_degrees) * (radius_cm + self.wheelbase / 2) / self.speed
        self._add(f"Arc {'left' if way == 'L' else 'right'} R={radius_cm:g}, {angle_degrees:g}°",
                  left, right, seconds)

    def build(self, shape, *, length=50, radius=25, angle=45,
              legs=5, laps=1, direction="L", custom=""):
        shape = shape.lower().strip()
        if direction not in ("L", "R"):
            raise ValueError("Circle direction must be L or R.")
        if shape in ("circle", "oval"):
            laps = int(laps)
            if not 1 <= laps <= 10:
                raise ValueError("Laps must be between 1 and 10.")
        if shape == "circle":
            for _ in range(laps):
                self.arc(direction, radius, 360)
        elif shape == "oval":
            for _ in range(laps):
                self.straight(length)
                self.arc(direction, radius, 180)
                self.straight(length)
                self.arc(direction, radius, 180)
        elif shape == "zigzag":
            legs = int(legs)
            if not 2 <= legs <= 30:
                raise ValueError("Zigzag legs must be between 2 and 30.")
            angle = _positive(angle, "Zigzag angle", 85)
            for i in range(legs):
                if i:
                    way = direction if i % 2 else ("R" if direction == "L" else "L")
                    self.pivot(way, angle if i == 1 else 2 * angle)
                self.straight(length)
        elif shape == "custom":
            lines = custom.splitlines()
            if not lines or not any(line.strip() and not line.strip().startswith('#') for line in lines):
                raise ValueError("Enter some custom commands first.")
            for line_no, raw in enumerate(lines, start=1):
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                bits = line.upper().split()
                try:
                    if len(bits) == 2 and bits[0] in ("F", "B"):
                        self.straight(float(bits[1]), reverse=(bits[0] == "B"))
                    elif len(bits) == 2 and bits[0] in ("L", "R"):
                        self.pivot(bits[0], float(bits[1]))
                    elif len(bits) == 4 and bits[0] == "ARC" and bits[1] in ("L", "R"):
                        self.arc(bits[1], float(bits[2]), float(bits[3]))
                    else:
                        raise ValueError("Expected 'F 50', 'B 20', 'L 90', or 'ARC R 25 180'")
                except (ValueError, OverflowError) as exc:
                    raise ValueError(f"Custom line {line_no}: {exc}") from exc
        else:
            raise ValueError("Choose zigzag, circle, oval or custom.")
        return list(self.parts)


def advance_pose(pose, segment, seconds, max_speed_cm_s, wheelbase_cm):
    """Advance an ideal (x,y,heading-radians) pose through some of a segment."""
    x, y, heading = pose
    t = max(0, min(float(seconds), segment.duration))
    vl = (segment.left / 255.0) * max_speed_cm_s
    vr = (segment.right / 255.0) * max_speed_cm_s
    v = (vl + vr) / 2.0
    omega = (vr - vl) / wheelbase_cm
    if abs(omega) < 1e-10:
        return (x + v * cos(heading) * t, y + v * sin(heading) * t, heading)
    new_heading = heading + omega * t
    return (x + (v / omega) * (sin(new_heading) - sin(heading)),
            y - (v / omega) * (cos(new_heading) - cos(heading)), new_heading)


def sample_path(segments, max_speed_cm_s, wheelbase_cm, steps_per_second=12):
    """Return array of (x, y) points for drawing an IDEAL target path."""
    pose = (0.0, 0.0, 0.0)
    points = [(0.0, 0.0)]
    for segment in segments:
        steps = max(2, min(500, int(segment.duration * steps_per_second)))
        start = pose
        for index in range(1, steps + 1):
            p = advance_pose(start, segment, segment.duration * index / steps,
                             max_speed_cm_s, wheelbase_cm)
            points.append((p[0], p[1]))
        pose = advance_pose(start, segment, segment.duration, max_speed_cm_s, wheelbase_cm)
    return points


def route_pose(segments, index, partial_s, max_speed_cm_s, wheelbase_cm):
    pose = (0.0, 0.0, 0.0)
    for i, segment in enumerate(segments):
        if i < index:
            pose = advance_pose(pose, segment, segment.duration, max_speed_cm_s, wheelbase_cm)
        elif i == index:
            return advance_pose(pose, segment, partial_s, max_speed_cm_s, wheelbase_cm)
    return pose
