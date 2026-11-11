"""Diagnostics unit and GUI integration tests; no physical BLE required."""
from __future__ import annotations

import queue
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics import DiagnosticReport, interpret_error, usb_port_diagnosis
from motor_control import MotorTelemetry
from ble_bridge import BLEBridge
from app import BuggyApp


class PureDiagnosisTests(unittest.TestCase):
    def test_report_does_not_claim_motor_validation(self):
        d = DiagnosticReport()
        d.start('HMSoft')
        d.set('scan', 'PASS', 'Found 2 BLE advertisements')
        self.assertEqual(d.checks['hardware'].status, 'MANUAL')
        self.assertIn('or wheel motion', d.export_text())
        self.assertIn('Found 2 BLE', d.export_text())
        self.assertEqual(d.checks['firmware'].status, 'PENDING')

    def test_error_advice_points_to_correct_layers(self):
        self.assertEqual(interpret_error('Characteristic missing')[0], 'gatt')
        self.assertEqual(interpret_error('BLE write failed')[0], 'write')
        self.assertEqual(interpret_error('Not installed')[0], 'runtime')
        self.assertEqual(interpret_error('Bluetooth radio is off')[0], 'scan')

    def test_usb_enumeration_is_safe_and_nonfatal(self):
        state, detail = usb_port_diagnosis()
        self.assertIn(state, ('PASS', 'WARN'))
        self.assertIsInstance(detail, str)

    def test_hm10_handshake_notification_accepts_fragmentation(self):
        b = BLEBridge()
        b._notification(None, b'H,')
        b._notification(None, b'13\r\nT,10,-20,D,7\n')
        e = []
        while not b.events.empty():
            e.append(b.events.get_nowait())
        self.assertTrue(any(kind == 'firmware_reply' for kind, _ in e))
        self.assertTrue(any(kind == 'telemetry' for kind, _ in e))
        b.close()


class DiagnosisUITests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = BuggyApp(self.root)
        self.root.update()
        self.p_scan = patch('app.BLEAK_ERROR', None)
        self.p_scan.start()
        self.scanned = []
        self.connected = []
        self.queries = []
        self.app.bridge.scan = lambda: self.scanned.append(True)
        self.app.bridge.connect = lambda d, u: self.connected.append((d, u))
        self.app.bridge.probe_firmware = lambda: self.queries.append(True)

    def tearDown(self):
        self.app._shutdown()
        self.p_scan.stop()
        self.root.update_idletasks()
        self.root.destroy()

    def events(self):
        self.app._events()
        if self.app.diagnostic_window is not None:
            self.app.diagnostic_window.refresh()

    def test_demo_marked_skipped_and_no_wireless(self):
        self.app.demo_var.set(True)
        self.app.run_diagnostics()
        self.assertFalse(self.scanned)
        self.assertEqual(self.app.diagnosis.checks['link'].status, 'SKIP')
        self.assertEqual(self.app.diagnosis.checks['hardware'].status, 'MANUAL')

    def test_scan_found_without_selection_never_autoconnects(self):
        self.app.run_diagnostics()
        self.assertTrue(self.scanned)
        d = SimpleNamespace(name='HMSoft', address='AA:BB')
        self.app.bridge.events.put(('devices', [d]))
        self.events()
        self.assertEqual(self.connected, [])
        self.assertEqual(self.app.diagnosis.checks['scan'].status, 'PASS')
        self.assertEqual(self.app.diagnosis.checks['device'].status, 'WARN')

    def test_full_selected_device_connect_handshake_and_telem(self):
        d = SimpleNamespace(name='HMSoft', address='AA:BB')
        self.app.devices['HMSoft — AA:BB'] = d
        self.app.device_var.set('HMSoft — AA:BB')
        self.app.run_diagnostics()
        self.app.bridge.events.put(('devices', [d]))
        self.events()
        self.assertEqual(self.connected, [(d, 'FFE1')])
        self.app.bridge.events.put(('gatt_ok', {'uuid': 'test-ffe1', 'write_mode': 'without response'}))
        self.app.bridge.events.put(('notify_ok', 'Subscriptions working'))
        self.app.bridge.events.put(('connected', 'HMSoft'))
        self.events()
        self.assertTrue(self.queries)
        self.app.bridge.events.put(('write_ok', 3))
        self.app.bridge.events.put(('telemetry', (MotorTelemetry(0, 0, 'ACTIVE BRAKE', 2), time.monotonic())))
        self.app.bridge.events.put(('firmware_reply', ('1.3', time.monotonic())))
        self.events()
        self.app._diagnostic_clock(time.monotonic() + 4.0)
        self.assertEqual(self.app.diagnosis.checks['link'].status, 'PASS')
        for key in ('gatt', 'notify', 'write', 'firmware', 'telemetry'):
            self.assertEqual(self.app.diagnosis.checks[key].status, 'PASS', key)
        self.assertFalse(self.app.diagnosis.is_running)
        self.assertTrue(self.app.brake_latched)

    def test_stale_firmware_no_ack_reports_old_or_uart_issue(self):
        self.app.online = True
        self.app.demo = False
        self.app.link_gatt = {'uuid': 'ffe1'}
        self.app.link_notify_state = 'PASS'
        self.app.run_diagnostics()
        self.app.bridge.events.put(('write_ok', 1))
        self.events()
        self.app._diagnostic_clock(time.monotonic() + 4)
        self.assertEqual(self.app.diagnosis.checks['firmware'].status, 'FAIL')
        self.assertEqual(self.app.diagnosis.checks['telemetry'].status, 'FAIL')
        self.assertIn('v1.6.3', self.app.diagnosis.advice())

    def test_diagnostics_window_and_keyboard_are_non_driving(self):
        self.app.open_diagnostics()
        self.app.diagnostic_window.refresh()
        self.app.start_keyboard_diagnosis()
        class Event:
            keysym = 'w'
            char = 'w'
            widget = self.app.drive_panel
        self.app._key_down(Event())
        self.assertEqual(self.app.diagnosis.checks['keyboard'].status, 'PASS')
        self.assertFalse(self.app.pressed)
        self.app.diagnostic_window.close()
        self.assertIsNone(self.app.diagnostic_window)

if __name__ == '__main__':
    unittest.main()
