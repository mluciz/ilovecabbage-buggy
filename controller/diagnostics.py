"""Deterministic diagnostic state and troubleshooting explanations.

PASS means a specific computer-observable test passed; it never means that
motors, batteries, or physical movement have been verified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import platform
import sys


STEPS = (
    ('runtime', 'Python / BLE dependency'),
    ('usb', 'USB Arduino COM ports (optional)'),
    ('scan', 'BLE scanner / adapter'),
    ('device', 'HM-10 device discovery'),
    ('link', 'BLE connection'),
    ('gatt', 'GATT UART write access'),
    ('notify', 'BLE notifications'),
    ('write', 'BLE transport write'),
    ('firmware', 'Arduino firmware handshake'),
    ('telemetry', 'Arduino feedback stream'),
    ('keyboard', 'Keyboard input'),
    ('hardware', 'Motor power and wiring'),
)
VALID = {'PENDING', 'PASS', 'WARN', 'FAIL', 'MANUAL', 'SKIP'}


@dataclass
class Check:
    name: str
    status: str = 'PENDING'
    detail: str = 'Not checked yet'


class DiagnosticReport:
    def __init__(self):
        self.checks = {key: Check(name) for key, name in STEPS}
        self.messages: list[str] = []
        self.started_at = None
        self.context = ''
        self.is_running = False

    def start(self, context: str = ''):
        self.started_at = datetime.now().astimezone().isoformat(timespec='seconds')
        self.messages = []
        self.context = context
        self.is_running = True
        self.checks = {key: Check(name) for key, name in STEPS}
        self.set('hardware', 'MANUAL', 'No motor current / wheel sensors; user must check hardware')
        self.add('Diagnostic run started (motors held in active brake).')

    def set(self, key: str, status: str, detail: str):
        if key not in self.checks or status not in VALID:
            raise ValueError(f'Invalid diagnosis entry: {key} / {status}')
        previous = self.checks[key]
        self.checks[key] = Check(previous.name, status, str(detail))
        if status != previous.status or str(detail) != previous.detail:
            self.add(f'{previous.name}: {status} — {detail}')

    def add(self, message: str):
        self.messages.append(f'[{datetime.now().astimezone():%H:%M:%S}] {message}')
        self.messages = self.messages[-400:]

    def advice(self):
        c = self.checks
        if c['runtime'].status == 'FAIL':
            return 'Install the required Python packages using run.bat. Check the Python interpreter / Python Tk installation.'
        if c['scan'].status == 'FAIL':
            return 'Windows Settings → Bluetooth & devices: switch Bluetooth on. Check Device Manager for a BLE-capable adapter, update its driver, then restart the app.'
        if c['device'].status in ('FAIL', 'WARN') and c['scan'].status == 'PASS':
            return 'The scanner works, but the HM-10 was not positively identified. Power the buggy, move it close to the laptop, disconnect any phone, rescan; it may be named HMSoft instead of cabbagelover.'
        if c['link'].status == 'FAIL':
            return 'Device was discovered but BLE could not connect. Disconnect other phones/apps, power-cycle the HM-10, retry nearby. Some HM-10 clones need a different GATT UUID.'
        if c['gatt'].status == 'FAIL':
            return 'Connected to BLE but the requested UART characteristic is missing or read-only. Inspect the discovered writable UUIDs and enter the right one in the app.'
        if c['notify'].status in ('WARN', 'FAIL'):
            return 'The characteristic cannot provide notifications. Commands may still work, but feedback and a verified handshake are unavailable. Check the HM-10 clone/service or use a notifiable UART characteristic.'
        if c['write'].status == 'FAIL':
            return 'BLE writes failed. The device may have disconnected or its writable characteristic changed. Reconnect and repeat the diagnostic scan.'
        if c['firmware'].status == 'FAIL':
            return 'BLE is connected, but no protocol Q→H,13 handshake arrived. Upload the supplied v1.6.3 Arduino sketch, check HM-10 TXD→Uno D2 and Uno D3→HM-10 RXD through the level shifter, common GND and UART baud (9600).'
        if c['firmware'].status == 'WARN':
            return 'Feedback exists but no Q→H,13 handshake was verified. Older firmware or dropped notifications may be responsible. Re-upload the v1.6.3 firmware and retry.'
        if c['telemetry'].status == 'FAIL':
            return 'No readable Arduino telemetry received. Verify notifications are enabled, v1.6.3 firmware is uploaded, HM-10 TX/RX wiring is crossed correctly and both sides use 9600 baud.'
        if c['telemetry'].status == 'WARN':
            return 'Arduino telemetry is stale or untested; BLE link alone does not guarantee the Arduino receives commands. Check power stability and wiring.'
        return 'Communication checks look healthy if marked PASS. Physical motion is still unverified: check driver VM battery power, VCC 5V, D4 STBY HIGH, common ground and motor outputs; run MotorTest.ino with wheels raised.'

    def summary(self):
        counts = {s: sum(c.status == s for c in self.checks.values()) for s in VALID}
        return f"{counts['PASS']} passed · {counts['WARN']} warnings · {counts['FAIL']} failures · {counts['PENDING']} pending · {counts['MANUAL']} manual"

    def export_text(self):
        output = [
            'BUGGY CONTROL CENTER v1.6.3 — DIAGNOSTIC REPORT',
            f'Generated: {datetime.now().astimezone().isoformat(timespec="seconds")}',
            f'Run started: {self.started_at or "not run"}',
            f'Environment: {platform.system()} {platform.release()} / Python {sys.version.split()[0]}',
            f'Context: {self.context}',
            self.summary(),
            '',
            'CHECK RESULTS (PASS means software-observed evidence, not physical motor operation):',
        ]
        for k, _ in STEPS:
            c = self.checks[k]
            output.append(f'[{c.status}] {c.name}: {c.detail}')
        output += ['', 'NEXT RECOMMENDED ACTION:', self.advice(), '', 'EVENT HISTORY:']
        output.extend(self.messages)
        output += ['', 'SAFETY: Diagnostic checks never prove battery voltage, motor RPM, or wheel motion.']
        return '\n'.join(output) + '\n'


def interpret_error(message: str):
    """Return stage, short likely cause, and a tangible next action."""
    m = message.lower()
    if 'not installed' in m or 'install ble' in m or 'no module named' in m:
        return 'runtime', 'BLE dependency is missing; run run.bat to install Bleak.'
    if any(k in m for k in ('not available', 'adapter', 'bluetooth is turned off', 'radio is off', 'device not found', 'unreachable')):
        return 'scan', 'Check Windows Bluetooth toggle, adapter/driver, and HM-10 power/range.'
    if any(k in m for k in ('characteristic', 'gatt', 'uuid', 'writable')):
        return 'gatt', 'Check the GATT characteristic UUID and writable properties; clones may differ.'
    if 'notify' in m or 'notification' in m:
        return 'notify', 'BLE UART notifications unavailable; feedback cannot be verified.'
    if 'write' in m:
        return 'write', 'BLE write failed. Stop motors and reconnect your device.'
    return 'link', 'BLE connection problem. Close other clients, power-cycle HM-10, then retry.'


def usb_port_diagnosis() -> tuple[str, str]:
    """Enumerate only: never open ports or interfere with Arduino IDE uploads."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return 'WARN', 'pyserial not installed; install from requirements.txt (BLE does not require USB)'
    except Exception as exc:
        return 'WARN', 'USB enumeration unavailable: ' + str(exc)
    try:
        ports = list(list_ports.comports())
    except Exception as exc:
        return 'WARN', 'Unable to list COM ports: ' + str(exc)
    if not ports:
        return 'WARN', 'No serial COM ports found; connect Uno with a DATA USB cable if uploading firmware'
    candidates = [port for port in ports if any(x in ((port.description or '') + ' ' +
                         (port.manufacturer or '')).lower() for x in ('arduino', 'ch340', 'usb serial', 'cp210'))]
    names = ', '.join(f'{p.device} ({p.description})' for p in (candidates or ports)[:8])
    return ('PASS' if candidates else 'WARN'), f'{len(ports)} COM port(s); ' + ('likely Uno: ' if candidates else 'Uno not identified: ') + names
