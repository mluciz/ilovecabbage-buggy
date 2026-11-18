"""Fast offline start-up preflight. Never opens a Bluetooth connection or moves motors."""
from __future__ import annotations

from datetime import datetime

from flight_recorder import offline_control_check
from link_stress_lab import offline_link_stress_check
from wheel_doctor import audit_sources


def run_preflight() -> tuple[bool, str]:
    sections = []
    checks = (
        ("SOURCE PIN + PROTOCOL MAP", audit_sources),
        ("MANUAL CONTROL MATH / PACKETS", offline_control_check),
        ("OFFLINE BLE LINK STRESS MODEL", offline_link_stress_check),
    )
    all_ok = True
    for title, fn in checks:
        try:
            result = fn()
            if title == "SOURCE PIN + PROTOCOL MAP":
                ok, output = result
                detail = "\n".join(output)
            else:
                ok, detail = result
            all_ok = all_ok and bool(ok)
            sections.append(f"[{'PASS' if ok else 'FAIL'}] {title}\n{detail}")
        except Exception as exc:
            all_ok = False
            sections.append(f"[FAIL] {title}\n{type(exc).__name__}: {exc}")
    result = [
        "CABBAGE CONTROL STUDIO / OFFLINE PRE-FLIGHT",
        f"UTC generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"OVERALL SOURCE/SIMULATION RESULT: {'PASS' if all_ok else 'FAIL'}",
        "",
        "NO BLE OR PHYSICAL MOTOR COMMANDS WERE SENT BY THIS TEST.",
        "PASS NEVER PROVES UNO BATTERY, HM-10 LINK, WHEEL RPM OR BRAKING.",
        "Always use the physical switch and raised-wheel checks before driving.",
        "",
        *sections
    ]
    return all_ok, "\n\n".join(result)
