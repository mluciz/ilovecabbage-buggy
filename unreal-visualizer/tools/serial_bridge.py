#!/usr/bin/env python3
"""OPTIONAL receive-only serial-to-UDP bridge for a dedicated sensor source.

This does not work with an arbitrary existing motor-control firmware.
Input must be one complete schema-2 JSON object per newline.
It never writes to the serial device or any motor.
"""
from __future__ import annotations
import argparse
import socket
import time
from telemetry_protocol import TelemetryError, decode_payload, encode_payload

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-port", required=True, help="e.g. COM8")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--port", type=int, default=48765)
    args = parser.parse_args()
    try:
        import serial
    except ImportError as error:
        raise SystemExit("Install the optional dependency first: py -m pip install pyserial") from error
    print("Dedicated sensor stream only. This script NEVER sends bytes back to the Arduino.")
    print("Do not share a serial port simultaneously with the main buggy controller.")
    good = bad = 0
    with serial.Serial(args.serial_port, args.baud, timeout=0.25, write_timeout=0) as source:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            try:
                while True:
                    line = source.readline(4097).strip()
                    if not line:
                        continue
                    try:
                        normalized = decode_payload(line)
                        normalized["source"] = "serial-sensor-bench"
                        udp.sendto(encode_payload(normalized), ("127.0.0.1", args.port))
                        good += 1
                    except TelemetryError as exc:
                        bad += 1
                        if bad < 4 or bad % 50 == 0:
                            print(f"Rejected invalid sensor line #{bad}: {exc}")
                    if good and good % 100 == 0:
                        print(f"Forwarded {good} valid packets; rejected {bad}")
            except KeyboardInterrupt:
                print(f"Stopped. Valid {good}, rejected {bad}")

if __name__ == "__main__":
    main()
