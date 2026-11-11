"""Deterministic virtual-link stress tests, absolutely no BLE or motor I/O.

The model covers command cadence, packet loss and the Arduino's watchdog/
re-arm policy, *not* radio throughput, motor voltage or real hardware timing.
"""
from __future__ import annotations

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class LinkScenario:
    name: str
    sent: int
    delivered: int
    max_gap_ms: int
    watchdog_trips: int
    stayed_locked_after_outage: bool


def simulate_link(name: str, duration_s=20.0, interval_s=0.10,
                  drop_every=0, blackout=None, jitter_s=0.015,
                  watchdog_s=1.2, seed=2026) -> LinkScenario:
    """Virtual stream: firmware only drives while freshly commanded and armed."""
    if duration_s <= 0 or interval_s <= 0 or watchdog_s <= 0 or jitter_s < 0:
        raise ValueError('Invalid simulation timing')
    rng = Random(seed)
    last_rx = 0.0
    time_s = 0.0
    count = delivered = trips = 0
    max_gap = 0.0
    locked = False
    while time_s < duration_s:
        time_s += max(0.001, interval_s + rng.uniform(-jitter_s, jitter_s))
        if time_s > duration_s:
            break
        count += 1
        in_blackout = blackout is not None and blackout[0] <= time_s < blackout[1]
        dropped = in_blackout or (drop_every > 0 and count % drop_every == 0)
        if not dropped:
            gap = time_s - last_rx
            max_gap = max(max_gap, gap)
            if gap > watchdog_s and not locked:
                trips += 1
                locked = True
            delivered += 1
            if not locked:
                last_rx = time_s
        elif not locked and time_s - last_rx > watchdog_s:
            trips += 1
            locked = True
    return LinkScenario(name, count, delivered, round(max_gap * 1000), trips, locked)


def offline_link_stress_check() -> tuple[bool, str]:
    normal = simulate_link('Ordinary jitter + 1/12 packet drop', drop_every=12)
    interruption = simulate_link('2-second simulated radio outage',
                                 blackout=(8.0, 10.0), drop_every=12)
    ok = normal.watchdog_trips == 0 and interruption.watchdog_trips == 1 \
         and interruption.stayed_locked_after_outage
    detail = (
        f'Virtual link (NO BUGGY / NO BLE):\n'
        f'• Routine jitter/loss: {normal.delivered}/{normal.sent} frames delivered; '
        f'max gap {normal.max_gap_ms} ms; watchdog trips {normal.watchdog_trips}.\n'
        f'• 2-second blackout: {interruption.delivered}/{interruption.sent} frames delivered; '
        f'watchdog trips {interruption.watchdog_trips}; '
        f'lockout until stop/re-arm: {interruption.stayed_locked_after_outage}.\n\n'
        'Synthetic proof of watchdog handling only, not a measurement of your HM-10 or motors.'
    )
    return ok, detail
