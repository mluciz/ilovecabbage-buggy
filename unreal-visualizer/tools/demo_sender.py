#!/usr/bin/env python3
"""Independent three-ToF demonstration sender; never sends any motor commands."""
from __future__ import annotations
import argparse
import math
import socket
import time
from telemetry_protocol import encode_payload

BOXES = (
    (180., 0., 30., 42.), (100., 150., 30., 35.),
    (105., -145., 33., 35.), (-150., 60., 45., 30.),
    (-145., -160., 24., 54.),
)
SENSORS = (("front", 0., 17., 0.), ("left", 55., 10., 10.), ("right", -55., 10., -10.))

def intersect_box(x: float, y: float, dx: float, dy: float, box: tuple[float, ...], maximum: float = 200.) -> float | None:
    cx, cy, hx, hy = box
    lo, hi = 0., maximum
    for origin, direction, centre, half in ((x, dx, cx, hx), (y, dy, cy, hy)):
        if abs(direction) < 1e-8:
            if not centre - half <= origin <= centre + half:
                return None
        else:
            a, b = (centre - half - origin) / direction, (centre + half - origin) / direction
            lo = max(lo, min(a, b))
            hi = min(hi, max(a, b))
            if lo > hi:
                return None
    hit = lo if lo > 0.01 else hi
    return hit if 2. <= hit <= maximum else None

def demo_packet(t: float, scenario: str = "arena") -> dict:
    if scenario not in ("arena", "sensor-dropout", "turning"):
        raise ValueError("unknown scenario")
    x = 20 * math.sin(t * .22)
    y = 16 * math.sin(t * .15)
    yaw = 13 * math.sin(t * .28) if scenario != "turning" else 65 * math.sin(t * .5)
    sensor_rows = []
    for idx, (name, mount, ox, oy) in enumerate(SENSORS):
        rad = math.radians(yaw)
        sx = x + ox * math.cos(rad) - oy * math.sin(rad)
        sy = y + ox * math.sin(rad) + oy * math.cos(rad)
        ray = math.radians(yaw + mount)
        dx, dy = math.cos(ray), math.sin(ray)
        hits = [h for b in BOXES if (h := intersect_box(sx, sy, dx, dy, b)) is not None]
        valid = bool(hits) and not (scenario == "sensor-dropout" and idx == 1 and int(t) % 6 < 3)
        row = {"id": name, "valid": valid}
        if valid:
            row["distance_mm"] = round(min(hits) * 10, 2)
        sensor_rows.append(row)
    return {"schema": 2, "source": "synthetic-demo", "sensors": sensor_rows,
            "pose": {"x_m": x / 100., "y_m": y / 100., "yaw_deg": yaw},
            "imu": {"gyro_z_dps": 3.64 * math.cos(t*.28), "dt_s": .05}}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=48765)
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--hz", type=float, default=12.)
    parser.add_argument("--duration", type=float, default=0., help="0 means continuous")
    parser.add_argument("--scenario", choices=("arena", "sensor-dropout", "turning"), default="arena")
    args = parser.parse_args()
    if not (0 < args.hz <= 40) or args.duration < 0:
        parser.error("hz must be (0,40] and duration must be nonnegative")
    print("READ-ONLY 3-ToF simulated telemetry. Switch Unreal dashboard to EXTERNAL UDP.")
    start = time.monotonic()
    count = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            while args.duration == 0 or time.monotonic() - start < args.duration:
                t = time.monotonic() - start
                payload = encode_payload(demo_packet(t, args.scenario))
                sock.sendto(payload, (args.host, args.port))
                count += 1
                if count % max(1, int(args.hz*5)) == 0:
                    print(f"Sent {count} schema-2 three-range packets")
                time.sleep(1. / args.hz)
        except KeyboardInterrupt:
            pass
    print(f"Stopped after {count} telemetry packets. No motors were controlled.")

if __name__ == "__main__":
    main()
