#!/usr/bin/env python3
"""Offline deterministic-looking demo telemetry. Never controls motors."""
import argparse
import json
import math
import socket
import time

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=48765)
    p.add_argument("--hz", type=float, default=12.0)
    args = p.parse_args()
    if not 0 < args.hz <= 60:
        p.error("--hz must be in (0, 60]")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    started = time.monotonic()
    print("Simulation ONLY: Ctrl+C to stop; no motor commands are sent.")
    try:
        while True:
            t = time.monotonic() - started
            yaw = 15 * math.sin(t / 4)
            # Demonstration shows a scan fan, not true inferred obstacle shapes.
            msg = {"schema": 1, "source": "simulation", "timestamp_s": time.time(),
                   "pose": {"x_m": .35 * math.sin(t / 7), "y_m": 0, "yaw_deg": yaw},
                   "imu": {"gyro_z_dps": 3.75 * math.cos(t / 4), "dt_s": 1 / args.hz},
                   "tof": {"valid": True, "distance_mm": 500 + 220 * math.sin(t * .5),
                           "sensor_yaw_deg": 35 * math.sin(t * .9)}}
            sock.sendto(json.dumps(msg, separators=(",", ":")).encode(), (args.host, args.port))
            time.sleep(1 / args.hz)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
