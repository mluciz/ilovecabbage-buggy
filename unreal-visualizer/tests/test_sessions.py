"""Local-only recording and replay tests: no Unreal, sensors or motors needed."""
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from session_tool import analyze, iter_session, replay, capture
from demo_sender import demo_packet
from telemetry_protocol import encode_payload

class SessionToolTests(unittest.TestCase):
    def test_inspect_valid_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "good.jsonl"
            with path.open("w") as stream:
                for t in (0., .1, .2):
                    stream.write(json.dumps({"t_s": t, "packet": demo_packet(t)}) + "\n")
            stats = analyze(iter_session(str(path)))
            self.assertEqual(stats["frames"], 3)
            self.assertEqual(stats["imu_frames"], 3)
            self.assertEqual(stats["duration_s"], .2)
            self.assertEqual(replay(file=str(path), dry_run=True)["sent"], 3)
    def test_replay_rejects_bad_tail_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.jsonl"
            path.write_text(json.dumps({"t_s": 0., "packet": demo_packet(0.)}) + "\n{}\n")
            with self.assertRaises(ValueError):
                replay(file=str(path))
    def test_reject_backward_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "reverse.jsonl"
            with path.open("w") as stream:
                for t in (.2, .1):
                    stream.write(json.dumps({"t_s": t, "packet": demo_packet(t)}) + "\n")
            with self.assertRaises(ValueError):
                list(iter_session(str(path)))
    def test_summary_dropouts_and_gaps(self):
        p = demo_packet(0.)
        for row in p["sensors"]: row["valid"] = False; row.pop("distance_mm", None)
        stats = analyze([(0.0, p), (.6, p)])
        self.assertEqual(stats["long_gaps_over_500ms"], 1)
        self.assertEqual(stats["sensor_summary"]["front"]["no_hit"], 2)
    def test_capture_rejects_same_port(self):
        with self.assertRaises(ValueError):
            capture(output="unused.jsonl", listen_port=48764, forward_port=48764)
    def test_replay_rejects_speed(self):
        with self.assertRaises(ValueError):
            replay(file="unused.jsonl", speed=0.)
    def test_roundtrip_real_loopback_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            out = str(Path(folder)/"captured.jsonl")
            ready = threading.Event()
            received = {}
            # Bind our own dynamic UDP port; capture() itself binds safely.
            holder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            holder.bind(("127.0.0.1", 0)); listen_port = holder.getsockname()[1]
            holder.close()
            sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sink.bind(("127.0.0.1", 0)); sink.settimeout(3.)
            output_port = sink.getsockname()[1]
            def worker():
                ready.set()
                received["result"] = capture(output=out, listen_port=listen_port,
                                             forward_port=output_port, max_packets=1, duration=3.)
            thread = threading.Thread(target=worker, daemon=True)
            thread.start(); ready.wait(1.)
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            raw = encode_payload(demo_packet(0.))
            try:
                for _ in range(12):
                    sender.sendto(raw, ("127.0.0.1", listen_port))
                    if not thread.is_alive(): break
                    time.sleep(.06)
                forwarded, _ = sink.recvfrom(8192)
                self.assertEqual(forwarded, raw)
            finally:
                sender.close(); sink.close(); thread.join(4.)
            self.assertFalse(thread.is_alive())
            self.assertEqual(received["result"]["accepted"], 1)
            self.assertEqual(analyze(iter_session(out))["frames"], 1)

if __name__ == "__main__":
    unittest.main()
