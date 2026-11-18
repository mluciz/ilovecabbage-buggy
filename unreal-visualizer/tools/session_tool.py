#!/usr/bin/env python3
"""Local-only capture, replay and analysis for Cabbage Spatial Lab.

Recording is a separate UDP proxy: sensors/demo -> 127.0.0.1:48764 (capture)
-> Unreal receive-only 127.0.0.1:48765. This avoids port-binding collisions.
No Bluetooth, serial writes, motor commands, cloud services or external hosts.
"""
from __future__ import annotations
import argparse
import json
import math
import socket
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable
from telemetry_protocol import decode_payload, encode_payload, TelemetryError

INPUT_PORT = 48764
OUTPUT_PORT = 48765
MAX_SESSION_LINE = 16384

def _safe_path(path: str) -> Path:
    target = Path(path).expanduser()
    if target.suffix.lower() != ".jsonl":
        raise ValueError("session filename must end with .jsonl")
    return target

def iter_session(path: str) -> Iterable[tuple[float, dict]]:
    """Reject corrupt/non-monotonic recording files before forwarding data."""
    previous = -1.0
    with _safe_path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if len(line.encode("utf-8")) > MAX_SESSION_LINE:
                raise ValueError(f"session line {line_number}: oversized")
            try:
                record = json.loads(line)
                offset = record["t_s"]
                if isinstance(offset, bool) or not isinstance(offset, (float, int)):
                    raise ValueError("t_s must be numeric")
                offset = float(offset)
                if not math.isfinite(offset) or offset < previous or offset < 0:
                    raise ValueError("non-monotonic time offset")
                packet = decode_payload(json.dumps(record["packet"]).encode("utf-8"))
            except (ValueError, TypeError, KeyError, TelemetryError) as exc:
                raise ValueError(f"session line {line_number}: {exc}") from exc
            previous = offset
            yield offset, packet

def analyze(records: Iterable[tuple[float, dict]]) -> dict[str, Any]:
    sensor_values: dict[str, list[float]] = {name: [] for name in ("front", "left", "right")}
    bad: dict[str, int] = {name: 0 for name in sensor_values}
    deltas: list[float] = []
    imu_frames = pose_frames = total = 0
    last = None
    first = None
    for offset, packet in records:
        if first is None: first = offset
        if last is not None: deltas.append(offset - last)
        last = offset
        total += 1
        imu_frames += int("imu" in packet)
        pose_frames += int("pose" in packet)
        for reading in packet["sensors"]:
            name = reading["id"]
            if reading["valid"]:
                sensor_values[name].append(reading["distance_mm"])
            else:
                bad[name] += 1
    return {
        "frames": total,
        "duration_s": round((last - first) if last is not None else 0., 3),
        "imu_frames": imu_frames,
        "external_pose_frames": pose_frames,
        "sensor_summary": {
            name: {
                "valid": len(values),
                "no_hit": bad[name],
                "min_mm": min(values) if values else None,
                "median_mm": round(statistics.median(values), 2) if values else None,
                "max_mm": max(values) if values else None
            }
            for name, values in sensor_values.items()
        },
        "interpacket_gap_ms_p95": round(sorted(deltas)[min(len(deltas)-1, int(.95*(len(deltas)-1)))]*1000, 1) if deltas else None,
        "long_gaps_over_500ms": sum(delta > .5 for delta in deltas)
    }

def capture(*, output: str, listen_port: int = INPUT_PORT, forward_port: int = OUTPUT_PORT,
            duration: float = 0., max_packets: int = 0) -> dict:
    if listen_port == forward_port:
        raise ValueError("capture must listen on a different port from Unreal")
    if duration < 0 or max_packets < 0:
        raise ValueError("duration and max_packets must be nonnegative")
    target = _safe_path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    accepted = dropped = 0
    start = time.monotonic()
    print(f"Capturing localhost:{listen_port} -> Unreal localhost:{forward_port}; writing {target}")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, \
         socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender, \
         target.open("x", encoding="utf-8") as output_stream:
        receiver.bind(("127.0.0.1", listen_port))
        receiver.settimeout(.25)
        try:
            while True:
                if duration and time.monotonic() - start >= duration:
                    break
                if max_packets and accepted >= max_packets:
                    break
                try:
                    raw, _ = receiver.recvfrom(8192)
                except socket.timeout:
                    continue
                try:
                    packet = decode_payload(raw)
                except TelemetryError:
                    dropped += 1
                    continue
                sender.sendto(encode_payload(packet), ("127.0.0.1", forward_port))
                record = {"t_s": round(time.monotonic() - start, 6), "packet": packet}
                output_stream.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
                accepted += 1
                if accepted % 200 == 0:
                    output_stream.flush()
                    print(f"accepted={accepted}, rejected={dropped}")
        except KeyboardInterrupt:
            pass
    return {"accepted": accepted, "rejected": dropped, "file": str(target)}

def replay(*, file: str, port: int = OUTPUT_PORT, speed: float = 1.,
           limit: int = 0, dry_run: bool = False) -> dict:
    if not .1 <= speed <= 8:
        raise ValueError("speed must be between 0.1 and 8")
    if limit < 0: raise ValueError("limit cannot be negative")
    # Validate complete session before emitting any packets; a corrupt tail
    # should not cause a partially replayed dataset.
    samples = list(iter_session(file))
    if limit: samples = samples[:limit]
    if not samples: return {"sent": 0, "duration_s": 0.0, "dry_run": dry_run}
    baseline = samples[0][0]
    started = time.monotonic()
    if not dry_run:
        print(f"Replaying {len(samples)} frames locally to 127.0.0.1:{port}, {speed}x speed")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for t, packet in samples:
            if not dry_run:
                target_time = started + (t - baseline) / speed
                sleep_s = target_time - time.monotonic()
                if sleep_s > 0: time.sleep(sleep_s)
                sock.sendto(encode_payload(packet), ("127.0.0.1", port))
    return {"sent": len(samples), "duration_s": round((samples[-1][0]-baseline)/speed, 3), "dry_run": dry_run}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture", help="record sensor UDP and forward to Unreal")
    c.add_argument("--out", required=True, help="new .jsonl file; will not overwrite")
    c.add_argument("--listen-port", type=int, default=INPUT_PORT)
    c.add_argument("--forward-port", type=int, default=OUTPUT_PORT)
    c.add_argument("--duration", type=float, default=0.)
    c.add_argument("--max-packets", type=int, default=0)
    r = sub.add_parser("replay", help="replay a validated recording to Unreal")
    r.add_argument("file")
    r.add_argument("--port", type=int, default=OUTPUT_PORT)
    r.add_argument("--speed", type=float, default=1.)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--dry-run", action="store_true")
    i = sub.add_parser("inspect", help="summarize sensor health and dropout from a recording")
    i.add_argument("file")
    args = parser.parse_args()
    try:
        if args.command == "capture":
            result = capture(output=args.out, listen_port=args.listen_port, forward_port=args.forward_port,
                             duration=args.duration, max_packets=args.max_packets)
        elif args.command == "replay":
            result = replay(file=args.file, port=args.port, speed=args.speed,
                            limit=args.limit, dry_run=args.dry_run)
        else:
            result = analyze(iter_session(args.file))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Spatial Lab: {exc}\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
