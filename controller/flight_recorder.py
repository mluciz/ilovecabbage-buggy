"""Bounded, human-readable command log for diagnosing unreliable drive systems.

Events are software observations only, not encoder/motor-voltage measurements.
"""
from __future__ import annotations

import csv
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import monotonic

from motor_control import manual_wheels, balance_wheels
from route_planner import GEARS


class FlightRecorder:
    def __init__(self, capacity=6000):
        self._events = deque(maxlen=capacity)
        self._lock = Lock()
        self._start = monotonic()

    @property
    def count(self):
        with self._lock:
            return len(self._events)

    def record(self, source, event, detail=''):
        row = (datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
               round(monotonic() - self._start, 3), str(source), str(event), str(detail))
        with self._lock:
            self._events.append(row)

    def snapshot(self):
        with self._lock:
            return list(self._events)

    def export_csv(self, path):
        output = Path(path)
        with output.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(('UTC_time', 'elapsed_seconds', 'source', 'event', 'details'))
            writer.writerows(self.snapshot())
        return output


def offline_control_check():
    """Pure software self-test; never connects, writes BLE, or energizes motors."""
    count = 0
    for gear, pwm in GEARS.items():
        for direction, expected in [({'W'}, (pwm, pwm)),
                                    ({'S'}, (-pwm, -pwm)),
                                    (set(), (0, 0)),
                                    ({'W', 'S'}, (0, 0))]:
            result = manual_wheels(direction, pwm, 50)
            if result != expected:
                return False, f'Gear {gear}: {direction} produced {result}, expected {expected}.'
            count += 1
        for direction in ({'A'}, {'D'}, {'W', 'A'}, {'W', 'D'}, {'S', 'A'}, {'S', 'D'}):
            l, r = manual_wheels(direction, pwm, 50)
            frame = f'M,{l},{r}\n'
            if not (-255 <= l <= 255 and -255 <= r <= 255 and len(frame) <= 16):
                return False, f'Gear {gear}: invalid motor command {frame!r}'
            count += 1
    if balance_wheels(220, 220, 30) != (154, 220):
        return False, 'Manual balance calibration calculation failed.'
    if balance_wheels(-220, -220, -30) != (-220, -154):
        return False, 'Reverse balance calibration calculation failed.'
    return True, f'{count + 2} control calculations and safety bounds passed.'
