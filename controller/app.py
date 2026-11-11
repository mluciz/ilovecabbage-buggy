"""Buggy Control Center — Windows / Python tkinter + Bluetooth Low Energy HM-10.

Run with: py app.py
"""
from __future__ import annotations

import math
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ble_bridge import BLEBridge, BLEAK_ERROR
from diagnostics import DiagnosticReport, interpret_error, usb_port_diagnosis
from diagnostic_window import DiagnosticWindow
from route_planner import Planner, GEARS, sample_path, route_pose
from motor_control import manual_wheels, balance_wheels
from flight_recorder import FlightRecorder, offline_control_check
from link_stress_lab import offline_link_stress_check

BG = '#0b1020'
CARD = '#141d30'
CARD_DARK = '#10182a'
BORDER = '#2c3850'
TEXT = '#f1f5ff'
MUTED = '#99abc7'
CYAN = '#55d9e9'
GREEN = '#4ddd9c'
AMBER = '#f5c26b'
RED = '#ff667e'
BLUE = '#447bd0'


class BuggyApp:
    def __init__(self, root):
        self.root = root
        root.title('Buggy Control Center v1.6.4 — Control Lab')
        root.geometry('1190x920')
        root.minsize(1050, 820)
        root.configure(bg=BG)

        self._closed = False
        self._tick_after = None
        self._preview_after = None
        self._focus_after = None
        self.bridge = BLEBridge()
        self.flight = FlightRecorder()
        self._last_tx_at = 0.0
        self._last_tx_ms = 0.0
        self._last_tx_payload = ""
        self.devices = {}
        self.online = False
        self.demo = False
        self.pressed = set()
        self._pressed_sources = {k: set() for k in 'WASD'}  # mouse and keyboard must not release each other
        self._pending_key_releases = {}  # Windows key auto-repeat generates fake KeyRelease events
        self._pending_block_releases = {}  # don't undo a brake latch on fake key-up
        self._blocked_drive_keys = set()  # Brake cannot be defeated by stale key repeats
        self._keyboard_pressed = set()  # physical key reconciliation, Windows only
        self._physical_key_misses = {}  # require repeated misses before releasing
        self._release_debounce_ms = 65
        self._feedback_warning_at = 0.0
        self._last_stream_warning_at = 0.0
        self.gear = 2
        self.route = []
        self.running = False
        self.route_index = 0
        self.segment_started = 0.0
        self.full_speed = 22.0
        self.wheelbase = 13.0
        self.brake_latched = True  # safe until explicit drive
        self.applied_left = 0.0
        self.applied_right = 0.0
        self._last_tick_at = time.monotonic()
        self.last_feedback = None
        self.last_feedback_at = 0.0
        self.rx_count = 0
        self.tx_count = 0
        self.telemetry_support = 'NOT CONNECTED'
        self.diagnosis = DiagnosticReport()
        self.diagnostic_window = None
        self.diag_phase = 'idle'
        self.diag_target = None
        self.diag_deadline = 0.0
        self.keyboard_test_active = False
        self.keyboard_test_deadline = 0.0
        self.link_gatt = None
        self.link_notify_state = None

        self.device_var = tk.StringVar()
        self.uuid_var = tk.StringVar(value='FFE1')
        self.demo_var = tk.BooleanVar(value=False)
        self.shape_var = tk.StringVar(value='Circle')
        self.turn_var = tk.StringVar(value='L')
        self.radius_var = tk.StringVar(value='25')
        self.length_var = tk.StringVar(value='60')
        self.legs_var = tk.StringVar(value='5')
        self.angle_var = tk.StringVar(value='45')
        self.laps_var = tk.StringVar(value='1')
        self.speed_var = tk.StringVar(value='22')
        self.width_var = tk.StringVar(value='13')
        self.status_var = tk.StringVar(value='DISCONNECTED')
        self.command_var = tk.StringVar(value='L 0   |   R 0')
        self.stats_var = tk.StringVar(value='Create a route to see its estimated duration.')
        self.progress_var = tk.StringVar(value='READY TO PREVIEW')
        self.keys_var = tk.StringVar(value='HELD KEYS: none')
        self.last_input_var = tk.StringVar(value='INPUT: waiting for keyboard — click ACTIVATE WASD')
        self.gear_info_var = tk.StringVar(value=f'GEAR {self.gear} / PWM {GEARS[self.gear]}')
        self.steering_var = tk.IntVar(value=50)
        self.precision_var = tk.BooleanVar(value=False)
        self.balance_var = tk.IntVar(value=0)  # 0=matched outputs, + favors right
        self.balance_info_var = tk.StringVar(value="MOTOR BALANCE 0% (equal)")
        self.link_health_var = tk.StringVar(value="COMMAND LINK: disconnected")
        self.steering_info_var = tk.StringVar(value='STEERING 50%')
        self.drive_state_var = tk.StringVar(value='ACTIVE BRAKE / STOPPED')
        self.telemetry_link_var = tk.StringVar(value='ARDUINO: NOT CONNECTED')
        self.telemetry_pwm_var = tk.StringVar(value='APPLIED BY ARDUINO: waiting for feedback')
        self.telemetry_state_var = tk.StringVar(value='DRIVER STATE: --')
        self.telemetry_age_var = tk.StringVar(value='FEEDBACK AGE: --')
        self.telemetry_packets_var = tk.StringVar(value='BLE TX: 0     ARDUINO RX: 0')


        self._make_style()
        self._build_ui()
        # Tk Scale does not consistently call command when IntVar is changed by code.
        self.steering_var.trace_add('write', lambda *_: self._steering_changed())
        self.balance_var.trace_add('write', lambda *_: self._balance_changed())
        self._bind_keys()
        self.root.protocol('WM_DELETE_WINDOW', self._quit)
        self._preview_after = self.root.after(180, self.preview_route)
        self._tick_after = self.root.after(80, self._tick)

    def _make_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Dark.TCombobox', fieldbackground=CARD_DARK, background=CARD_DARK,
                        foreground=TEXT, arrowcolor=CYAN, bordercolor=BORDER, padding=6)
        style.map('Dark.TCombobox', fieldbackground=[('readonly', CARD_DARK)],
                  foreground=[('readonly', TEXT)])

    def _label(self, parent, text, *, size=10, bold=False, color=TEXT, **kwargs):
        return tk.Label(parent, text=text, fg=color, bg=parent.cget('bg'),
                        font=('Segoe UI', size, 'bold' if bold else 'normal'), **kwargs)

    def _panel(self, parent, title=None):
        panel = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        if title:
            self._label(panel, title, size=11, bold=True).pack(anchor='w', padx=15, pady=(12, 8))
        return panel

    def _button(self, parent, text, command, *, color=BLUE, width=12, height=1):
        return tk.Button(parent, text=text, command=command, bg=color, fg='white',
                         activebackground=CYAN, activeforeground=BG, relief='flat',
                         bd=0, cursor='hand2', width=width, height=height,
                         font=('Segoe UI', 10, 'bold'))

    def _entry(self, parent, variable, width=9):
        entry = tk.Entry(parent, textvariable=variable, bg=CARD_DARK, fg=TEXT,
                         insertbackground=TEXT, relief='flat', highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=CYAN,
                         font=('Segoe UI', 10), width=width)
        entry.bind('<FocusIn>', lambda _e: self._typing_focused())
        return entry

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill='x', padx=20, pady=(15, 8))
        tk.Label(header, text='BUGGY', fg=CYAN, bg=BG,
                 font=('Segoe UI', 26, 'bold')).pack(side='left')
        tk.Label(header, text=' / CONTROL CENTER', fg=TEXT, bg=BG,
                 font=('Segoe UI', 17, 'bold')).pack(side='left', pady=(6, 0))
        tk.Label(header, textvariable=self.status_var, fg=AMBER, bg=BG,
                 font=('Segoe UI', 11, 'bold')).pack(side='right', pady=(8, 0))

        bar = self._panel(self.root)
        bar.pack(fill='x', padx=20, pady=(0, 12))
        row = tk.Frame(bar, bg=CARD)
        row.pack(fill='x', padx=12, pady=11)
        self._button(row, 'SCAN BLE', self.scan, color='#305c91', width=10).pack(side='left', padx=(0, 10))
        self.device_combo = ttk.Combobox(row, textvariable=self.device_var,
                                          style='Dark.TCombobox', state='readonly', width=31)
        self.device_combo.pack(side='left', padx=(0, 12))
        self._label(row, 'GATT UUID', color=MUTED).pack(side='left', padx=(0, 6))
        self._entry(row, self.uuid_var, 8).pack(side='left', padx=(0, 12))
        tk.Checkbutton(row, text='Demo mode', variable=self.demo_var, bg=CARD, fg=MUTED,
                       selectcolor=CARD_DARK, activebackground=CARD, activeforeground=TEXT,
                       font=('Segoe UI', 10)).pack(side='left', padx=(0, 12))
        self.connect_btn = self._button(row, 'CONNECT', self.toggle_connection,
                                         color='#197f83', width=12)
        self.connect_btn.pack(side='left')
        self._button(row, 'DIAGNOSTICS', self.open_diagnostics, color='#6b528f',
                     width=13).pack(side='left', padx=(10, 0))

        work = tk.Frame(self.root, bg=BG)
        work.pack(fill='both', expand=True, padx=20)
        left_outer = tk.Frame(work, bg=BG, width=405)
        left_outer.pack(side='left', fill='y', padx=(0, 12))
        left_outer.pack_propagate(False)
        left_scrollbar = tk.Scrollbar(left_outer, orient='vertical', width=11)
        left_scrollbar.pack(side='right', fill='y')
        left_canvas = tk.Canvas(left_outer, bg=BG, highlightthickness=0,
                                yscrollcommand=left_scrollbar.set)
        left_canvas.pack(side='left', fill='both', expand=True)
        left_scrollbar.config(command=left_canvas.yview)
        left = tk.Frame(left_canvas, bg=BG)
        left_id = left_canvas.create_window((0, 0), window=left, anchor='nw')
        left.bind('<Configure>', lambda _e: left_canvas.configure(
                  scrollregion=left_canvas.bbox('all')))
        left_canvas.bind('<Configure>', lambda e: left_canvas.itemconfigure(
                         left_id, width=e.width))
        self.left_canvas = left_canvas
        self.left_outer = left_outer
        self.root.bind_all('<MouseWheel>', self._scroll_left)
        right = tk.Frame(work, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        manual = self._panel(left, '01   MANUAL DRIVE  /  WASD')
        manual.configure(takefocus=1)
        self.drive_panel = manual
        manual.pack(fill='x', pady=(0, 10))
        self._label(manual, 'Hold keys to move · diagonals steer · release to stop',
                    size=9, color=MUTED).pack(anchor='w', padx=15)
        pads = tk.Frame(manual, bg=CARD)
        pads.pack(pady=8)
        keys = [('W', 0, 1), ('A', 1, 0), ('S', 1, 1), ('D', 1, 2)]
        for key, r, c in keys:
            btn = tk.Button(pads, text=key, bg='#263851', fg=TEXT, width=6, height=2,
                            relief='flat', font=('Segoe UI', 12, 'bold'), bd=0)
            btn.grid(row=r, column=c, padx=3, pady=3)
            btn.bind('<ButtonPress-1>', lambda _e, k=key: self._press(k, source='mouse'))
            btn.bind('<ButtonRelease-1>', lambda _e, k=key: self._release(k, source='mouse'))
            btn.bind('<Leave>', lambda _e, k=key: self._release(k, source='mouse'))
        gears = tk.Frame(manual, bg=CARD)
        gears.pack(fill='x', padx=15, pady=(0, 12))
        self._label(gears, 'GEAR', color=MUTED).pack(side='left', padx=(0, 8))
        self.gear_buttons = {}
        for gear in range(1, 5):
            b = self._button(gears, str(gear), lambda g=gear: self.set_gear(g),
                             color='#24354b', width=4)
            b.pack(side='left', padx=4)
            self.gear_buttons[gear] = b
        self._paint_gears()
        focus_row = tk.Frame(manual, bg=CARD)
        focus_row.pack(fill='x', padx=15, pady=(0, 8))
        self._button(focus_row, 'ACTIVATE WASD', self.activate_keyboard,
                     color='#197f83', width=17).pack(side='left')
        tk.Label(focus_row, textvariable=self.gear_info_var, fg=CYAN, bg=CARD,
                 font=('Consolas', 9, 'bold')).pack(side='left', padx=(10, 0))
        self._button(manual, 'BRAKE NOW [SPACE / ESC]', self.emergency_stop,
                     color='#ae3651', width=22).pack(fill='x', padx=15, pady=(0, 5))
        self._button(manual, 'OFFLINE CONTROL CHECK', self.run_offline_check,
                     color='#345476', width=22).pack(fill='x', padx=15, pady=(0, 5))
        self._button(manual, 'OFFLINE LINK STRESS', self.run_link_stress_check,
                     color='#345476', width=22).pack(fill='x', padx=15, pady=(0, 5))
        tk.Checkbutton(manual, text='Precision drive (optional, slower distinct gears)',
                       variable=self.precision_var, command=self._precision_changed,
                       bg=CARD, fg=CYAN, selectcolor=CARD_DARK,
                       activebackground=CARD, activeforeground=TEXT,
                       font=('Segoe UI', 9)).pack(anchor='w', padx=15, pady=(0, 5))
        tk.Label(manual, textvariable=self.keys_var, fg=GREEN, bg=CARD,
                 font=('Consolas', 9, 'bold')).pack(anchor='w', padx=15)
        tk.Label(manual, textvariable=self.last_input_var, fg=MUTED, bg=CARD,
                 wraplength=366, justify='left', font=('Segoe UI', 9)).pack(
                     anchor='w', padx=15, pady=(2, 6))

        tuning = tk.Frame(manual, bg=CARD)
        tuning.pack(fill='x', padx=15, pady=(1, 8))
        for label_var, value_var, min_val, max_val, callback in [
            (self.steering_info_var, self.steering_var, 0, 100, self._steering_changed),
        ]:
            line = tk.Frame(tuning, bg=CARD)
            line.pack(fill='x', pady=(1, 2))
            tk.Label(line, textvariable=label_var, bg=CARD, fg=CYAN,
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w')
            tk.Scale(line, from_=min_val, to=max_val, resolution=1, orient='horizontal',
                     variable=value_var, command=callback, showvalue=False,
                     bg=CARD, fg=TEXT, troughcolor='#293950', activebackground=CYAN,
                     highlightthickness=0, borderwidth=0, sliderrelief='flat',
                     length=342).pack(fill='x')
        balance_line = tk.Frame(manual, bg=CARD)
        balance_line.pack(fill='x', padx=15, pady=(1, 7))
        tk.Label(balance_line, textvariable=self.balance_info_var, bg=CARD, fg=CYAN,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        tk.Scale(balance_line, from_=-30, to=30, resolution=1, orient='horizontal',
                 variable=self.balance_var, command=lambda _v: self._balance_changed(),
                 bg=CARD, fg=TEXT, troughcolor='#293950', showvalue=False,
                 activebackground=CYAN, highlightthickness=0, borderwidth=0,
                 length=342).pack(fill='x')
        self._label(manual, 'Balance only changes MANUAL PWM, not auto tracks or motor wiring.',
                    size=8, color=MUTED).pack(anchor='w', padx=15, pady=(0, 5))
        self._label(manual, 'KEY RELEASE = ACTIVE BRAKE · SPACE / STOP = ACTIVE BRAKE',
                    color=AMBER, size=8).pack(anchor='w', padx=15, pady=(0, 12))

        auto = self._panel(left, '02   AUTOMATIC TRACKS')
        auto.pack(fill='both', expand=True)
        shape_row = tk.Frame(auto, bg=CARD)
        shape_row.pack(fill='x', padx=15, pady=(0, 10))
        self._label(shape_row, 'Track type', color=MUTED).pack(side='left')
        shape_combo = ttk.Combobox(shape_row, textvariable=self.shape_var,
                                    values=['Circle', 'Oval', 'Zigzag', 'Custom'],
                                    style='Dark.TCombobox', state='readonly', width=16)
        shape_combo.pack(side='right')
        shape_combo.bind('<<ComboboxSelected>>', lambda _e: self.preview_route())
        fields = tk.Frame(auto, bg=CARD)
        fields.pack(fill='x', padx=15)
        fields.grid_columnconfigure(0, weight=1)
        fields.grid_columnconfigure(2, weight=1)
        specs = [('Radius (cm)', self.radius_var), ('Straight / leg (cm)', self.length_var),
                 ('Zigzag angle (°)', self.angle_var), ('Zigzag legs', self.legs_var),
                 ('Laps', self.laps_var)]
        for i, (label, var) in enumerate(specs):
            r = i // 2
            c = (i % 2) * 2
            self._label(fields, label, color=MUTED, size=9).grid(row=r * 2, column=c,
                                                                  sticky='w', pady=(5, 3))
            self._entry(fields, var, 11).grid(row=r * 2 + 1, column=c, sticky='w', pady=(0, 5))
        turn = tk.Frame(auto, bg=CARD)
        turn.pack(fill='x', padx=15, pady=(3, 5))
        self._label(turn, 'Direction', color=MUTED, size=9).pack(side='left', padx=(0, 10))
        for text, val in [('Left / CCW', 'L'), ('Right / CW', 'R')]:
            tk.Radiobutton(turn, text=text, value=val, variable=self.turn_var,
                           bg=CARD, fg=TEXT, selectcolor=CARD_DARK, activebackground=CARD,
                           activeforeground=TEXT, font=('Segoe UI', 9),
                           command=self.preview_route).pack(side='left', padx=3)

        self._label(auto, 'Custom commands: F 50 / B 20 / L 90 / ARC R 25 180',
                    size=8, color=MUTED).pack(anchor='w', padx=15, pady=(1, 3))
        self.custom_text = tk.Text(auto, height=3, bg=CARD_DARK, fg=TEXT, insertbackground=TEXT,
                                   relief='flat', highlightthickness=1,
                                   highlightbackground=BORDER, font=('Consolas', 10),
                                   wrap='none')
        self.custom_text.pack(fill='x', padx=15)
        self.custom_text.insert('1.0', 'F 60\nARC L 25 180\nF 60')
        self.custom_text.bind('<FocusIn>', lambda _e: self._typing_focused())

        calibration = tk.Frame(auto, bg=CARD)
        calibration.pack(fill='x', padx=15, pady=(9, 8))
        for label, variable in [('Measured gear-4 speed (cm/s)', self.speed_var),
                                ('Wheel spacing (cm)', self.width_var)]:
            line = tk.Frame(calibration, bg=CARD)
            line.pack(fill='x', pady=2)
            self._label(line, label, size=9, color=MUTED).pack(side='left')
            self._entry(line, variable, 7).pack(side='right')
        actions = tk.Frame(auto, bg=CARD)
        actions.pack(fill='x', padx=15, pady=(4, 14))
        self._button(actions, 'PREVIEW', self.preview_route, color='#325373', width=11).pack(side='left')
        self._button(actions, 'START ROUTE', self.start_route, color='#16876c', width=12).pack(side='left', padx=8)
        self._button(actions, 'STOP', self.emergency_stop, color='#b3324d', width=8).pack(side='right')

        preview_panel = self._panel(right)
        preview_panel.pack(fill='both', expand=True)
        preview_head = tk.Frame(preview_panel, bg=CARD)
        preview_head.pack(fill='x', padx=15, pady=(12, 7))
        self._label(preview_head, '03   TRACK PREVIEW', bold=True, size=11).pack(side='left')
        self._label(preview_head, 'IDEAL ESTIMATE · NOT GPS / ODOMETRY',
                    color=AMBER, size=9).pack(side='right')
        self.preview = tk.Canvas(preview_panel, bg=CARD_DARK, highlightthickness=0, height=255)
        self.preview.pack(fill='both', expand=True, padx=14, pady=(0, 8))
        self.preview.bind('<Configure>', lambda _e: self.draw_preview())
        self._label(preview_panel, '', size=1).pack()
        tk.Label(preview_panel, textvariable=self.stats_var, bg=CARD, fg=MUTED,
                 font=('Segoe UI', 10)).pack(anchor='w', padx=15, pady=(0, 4))
        tk.Label(preview_panel, textvariable=self.progress_var, bg=CARD, fg=CYAN,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(0, 12))

        dashboard = self._panel(right, '04   LIVE TELEMETRY / BRAKING')
        dashboard.pack(fill='x', pady=(10, 0))
        dash_body = tk.Frame(dashboard, bg=CARD)
        dash_body.pack(fill='x', padx=15, pady=(0, 12))
        tk.Label(dash_body, textvariable=self.command_var, fg=GREEN, bg=CARD,
                 font=('Consolas', 12, 'bold')).pack(anchor='w')
        tk.Label(dash_body, textvariable=self.drive_state_var, fg=AMBER, bg=CARD,
                 font=('Consolas', 10, 'bold')).pack(anchor='w', pady=(1, 3))
        tk.Label(dash_body, textvariable=self.link_health_var, fg=CYAN, bg=CARD,
                 font=('Consolas', 9)).pack(anchor='w')
        tk.Label(dash_body, textvariable=self.telemetry_link_var, fg=CYAN, bg=CARD,
                 font=('Consolas', 10, 'bold')).pack(anchor='w')
        tk.Label(dash_body, textvariable=self.telemetry_pwm_var, fg=TEXT, bg=CARD,
                 font=('Consolas', 10)).pack(anchor='w')
        tk.Label(dash_body, textvariable=self.telemetry_state_var, fg=MUTED, bg=CARD,
                 font=('Consolas', 10)).pack(anchor='w')
        self.telemetry_bars = tk.Canvas(dash_body, height=44, bg=CARD_DARK,
                                        highlightthickness=0)
        self.telemetry_bars.pack(fill='x', pady=(4, 2))
        self.telemetry_bars.bind('<Configure>', lambda _e: self._redraw_telemetry_bars())
        status_row = tk.Frame(dash_body, bg=CARD)
        status_row.pack(fill='x', pady=(2, 0))
        tk.Label(status_row, textvariable=self.telemetry_age_var, fg=MUTED, bg=CARD,
                 font=('Consolas', 9)).pack(side='left')
        tk.Label(status_row, textvariable=self.telemetry_packets_var, fg=MUTED, bg=CARD,
                 font=('Consolas', 9)).pack(side='right')
        self._label(dash_body, 'PWM/accepted commands = firmware only, NOT measured wheel RPM.',
                    color=AMBER, size=8).pack(anchor='w', pady=(6, 0))
        self._label(dash_body, 'BLE drive ~120 ms · idle ~300 ms · Arduino telemetry pauses while moving',
                    color=MUTED, size=8).pack(anchor='w', pady=(1, 0))

        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill='x', padx=20, pady=(10, 16))
        log_head = tk.Frame(bottom, bg=BG)
        log_head.pack(fill='x')
        self._label(log_head, 'EVENT LOG · COMMAND FLIGHT RECORDER', color=MUTED, bold=True, size=9).pack(side='left')
        self._button(log_head, 'EXPORT TRACE CSV', self.export_trace, color='#325373', width=18).pack(side='right')
        self.log_text = tk.Text(bottom, height=2, bg=CARD, fg=MUTED,
                                insertbackground=TEXT, relief='flat', padx=10, pady=5,
                                font=('Consolas', 9), state='disabled')
        self.log_text.pack(fill='x', pady=(4, 0))
        self.log('Open Demo mode to explore without your buggy, or SCAN BLE to connect.')

    def log(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
        if self.diagnosis.started_at:
            self.diagnosis.add(str(message))

    def open_diagnostics(self):
        if self.diagnostic_window is None:
            self.diagnostic_window = DiagnosticWindow(self)
        else:
            self.diagnostic_window.top.lift()
            self.diagnostic_window.top.focus_force()

    def _finish_diagnostics(self):
        if self.diagnosis.is_running:
            for key, check in list(self.diagnosis.checks.items()):
                if key not in ('keyboard',) and check.status == 'PENDING':
                    self.diagnosis.set(key, 'SKIP', 'Not reached / not independently verified')
        self.diag_phase = 'idle'
        self.diagnosis.is_running = False
        self.brake_latched = True
        self.bridge.set_brake()
        self.diagnosis.add('Diagnostic run completed; brake remains latched.')

    def run_diagnostics(self):
        # No automatic motor pulse: safer to prove communication first.
        self.emergency_stop(quiet=True)
        self.keyboard_test_active = False
        self.diag_target = self.devices.get(self.device_var.get())
        self.diagnosis.start(f'Device selection: {self.device_var.get() or "none"}; UUID: {self.uuid_var.get()}; demo: {self.demo or self.demo_var.get()}')
        if BLEAK_ERROR:
            self.diagnosis.set('runtime', 'FAIL', 'Bleak import failed: ' + BLEAK_ERROR)
            self._finish_diagnostics()
            return
        self.diagnosis.set('runtime', 'PASS', 'Python runtime and Bleak imported successfully')
        self.diagnosis.set('keyboard', 'MANUAL', 'Click TEST KEYBOARD and press WASD / 1–4 to verify input')
        if self.demo or self.demo_var.get():
            for name in ('scan', 'device', 'link', 'gatt', 'notify', 'write', 'firmware', 'telemetry'):
                self.diagnosis.set(name, 'SKIP', 'Demo mode cannot verify physical Bluetooth hardware')
            self.diagnosis.add('Disable Demo mode to test the actual BLE link.')
            self._finish_diagnostics()
        elif self.online:
            self.diagnosis.set('scan', 'SKIP', 'Already connected — avoid scanning while a BLE link is active')
            self.diagnosis.set('device', 'PASS', 'Selected BLE device already connected')
            self.diagnosis.set('link', 'PASS', 'BLE link connected')
            if self.link_gatt:
                self.diagnosis.set('gatt', 'PASS', 'Writable UART characteristic: ' + self.link_gatt['uuid'])
            if self.link_notify_state == 'PASS':
                self.diagnosis.set('notify', 'PASS', 'BLE notifications successfully subscribed')
            elif self.link_notify_state == 'WARN':
                self.diagnosis.set('notify', 'WARN', 'Notifications unavailable; cannot verify firmware replies')
            self._start_firmware_probe()
        else:
            self.diag_phase = 'scan'
            self.diag_deadline = time.monotonic() + 15
            self.bridge.scan()

    def _diagnostic_scan_finished(self, found):
        if not self.diagnosis.is_running:
            return
        if not found:
            self.diagnosis.set('scan', 'WARN', 'BLE scan completed; no advertising devices detected')
            self.diagnosis.set('device', 'WARN', 'HM-10 not found. Check power, proximity and adapter.')
            self._finish_diagnostics()
            return
        self.diagnosis.set('scan', 'PASS', f'BLE scanner returned {len(found)} advertising device(s)')
        # Auto-connect only if the user had explicitly selected a device BEFORE running.
        selected = next((d for d in found if self.diag_target is not None and
                         d.address == self.diag_target.address), None)
        if selected is not None:
            self.diagnosis.set('device', 'PASS', f'Selected target found: {selected.name or "unnamed BLE device"}')
            self.diag_phase = 'connect'
            self.diag_deadline = time.monotonic() + 25
            self.bridge.connect(selected, self.uuid_var.get())
            return
        likely = [d for d in found if any(x in (d.name or '').lower() for x in ('hmsoft', 'hm-10', 'hm10', 'cabbagelover'))]
        if likely:
            self.diagnosis.set('device', 'WARN', f'{len(likely)} possible HM-10 detected; select it in the main window then rerun')
        else:
            self.diagnosis.set('device', 'WARN', 'No clearly named HM-10. It may advertise under a generic name.')
        for name in ('link', 'gatt', 'notify', 'write', 'firmware', 'telemetry'):
            self.diagnosis.set(name, 'SKIP', 'Choose the intended BLE device in the dropdown, then RUN again')
        self._finish_diagnostics()

    def _start_firmware_probe(self):
        if not self.diagnosis.is_running:
            return
        self.diag_phase = 'probe'
        self.diag_deadline = time.monotonic() + 3.6
        self.diagnosis.set('firmware', 'PENDING', 'Waiting for safe Q→H,13 response from Arduino')
        self.diagnosis.set('telemetry', 'PENDING', 'Waiting for a valid T,left,right,state,sequence notification')
        if self.last_feedback and time.monotonic() - self.last_feedback_at < 1.5:
            self.diagnosis.set('telemetry', 'PASS', 'Valid, recent Arduino PWM command telemetry received')
        self.bridge.probe_firmware()

    def _diagnostic_clock(self, now):
        if self.keyboard_test_active and now > self.keyboard_test_deadline:
            self.keyboard_test_active = False
            self.diagnosis.set('keyboard', 'WARN', 'No keyboard event detected within 12s. Click this window, then retry.')
        if not self.diagnosis.is_running or now < self.diag_deadline:
            return
        if self.diag_phase == 'probe':
            firmware = self.diagnosis.checks['firmware']
            telem = self.diagnosis.checks['telemetry']
            notify = self.diagnosis.checks['notify']
            if telem.status == 'PENDING':
                self.diagnosis.set('telemetry', 'WARN' if notify.status != 'PASS' else 'FAIL',
                                   'No parseable Arduino T message during probe period')
            if firmware.status == 'PENDING':
                state = 'WARN' if telem.status == 'PASS' or notify.status != 'PASS' else 'FAIL'
                self.diagnosis.set('firmware', state,
                                   'No H,13 reply received. Firmware may be old, UART path faulty, or notifications unavailable.')
            self._finish_diagnostics()
        elif self.diag_phase == 'scan':
            self.diagnosis.set('scan', 'FAIL', 'BLE scan did not finish within 15s')
            self._finish_diagnostics()
        elif self.diag_phase == 'connect':
            self.diagnosis.set('link', 'FAIL', 'BLE connect did not finish within 25s')
            self._finish_diagnostics()

    def start_keyboard_diagnosis(self):
        self.emergency_stop(quiet=True)
        self.keyboard_test_active = True
        self.keyboard_test_deadline = time.monotonic() + 12
        self.diagnosis.set('keyboard', 'PENDING', 'Press W, A, S, D or gear 1–4 now; movement is suppressed')
        self.diagnosis.add('Keyboard capture active for 12 seconds; buggy held in brake.')
        if self.diagnostic_window is not None:
            self.diagnostic_window.top.focus_force()

    def export_trace(self):
        """Export command and BLE feedback history, without claiming wheel-speed data."""
        if self.online and not self.demo and (self.pressed or self.running):
            self.emergency_stop()  # Never pause the GUI for a file dialog while driving.
            self.log('Stopped motors before opening the trace export dialog.')
        if not self.flight.count:
            messagebox.showinfo('No trace yet', 'No control events have been recorded yet.')
            return
        filename = filedialog.asksaveasfilename(
            defaultextension='.csv', filetypes=[('CSV trace', '*.csv')],
            initialfile=f'buggy_trace_{time.strftime("%Y%m%d_%H%M%S")}.csv',
            title='Export Buggy Control Center flight recorder')
        if filename:
            self.flight.export_csv(filename)
            self.log(f'Saved {self.flight.count} recent diagnostic events to {filename}')

    def run_link_stress_check(self):
        """Offline deterministic model. Never energizes the buggy."""
        if self.online and not self.demo:
            messagebox.showwarning('Disconnect first',
                                   'The synthetic stress test is only available disconnected or in Demo mode.')
            return
        ok, details = offline_link_stress_check()
        self.flight.record('OFFLINE', 'LINK_STRESS_PASS' if ok else 'LINK_STRESS_FAIL', details)
        self.log('Offline link stress simulation ' + ('passed' if ok else 'FAILED'))
        messagebox.showinfo('Offline link stress (synthetic)', details)

    def _precision_changed(self):
        # Never silently alter a motor's live PWM while the user is moving.
        if self.pressed and self.online:
            self.emergency_stop(quiet=True)
            self.log('Drive mode changed: safety brake. Release keys, then drive again.')
        self.gear_info_var.set(self._gear_caption())
        self._display_manual_command()

    def _gear_caption(self):
        value = self._manual_pwm()
        return f'GEAR {self.gear} / PWM {value}' + (' (PRECISION)' if self.precision_var.get() else '')

    def _manual_pwm(self):
        precision = {1: 110, 2: 150, 3: 200, 4: 240}
        return precision[self.gear] if self.precision_var.get() else GEARS[self.gear]

    def run_offline_check(self):
        """No drive commands; checks command calculations and packet formatting."""
        if self.online and not self.demo:
            messagebox.showwarning('Offline only',
                'Disconnect the real buggy before running the offline control check.')
            return
        ok, details = offline_control_check()
        self.flight.record('OFFLINE_CHECK', 'PASS' if ok else 'FAIL', details)
        self.log(('PASS' if ok else 'FAIL') + ': offline control check — ' + details)
        messagebox.showinfo('Offline control check' if ok else 'Control check FAILED',
                            details + '\n\nNo Bluetooth or motor commands were sent.')

    def _physical_key_down(self, key):
        """Return physical Windows key state, or None if not available."""
        try:
            import sys
            if sys.platform == 'win32' and key in 'WASD' and len(key) == 1:
                import ctypes
                return bool(ctypes.windll.user32.GetAsyncKeyState(ord(key)) & 0x8000)
        except (AttributeError, OSError):
            pass
        return None

    def _scroll_left(self, event):
        # Scroll route controls only while the pointer is within the left panel.
        lx, ly = self.left_outer.winfo_rootx(), self.left_outer.winfo_rooty()
        if lx <= event.x_root < lx + self.left_outer.winfo_width() and \
           ly <= event.y_root < ly + self.left_outer.winfo_height():
            self.left_canvas.yview_scroll(-int(event.delta / 120), 'units')

    def _bind_keys(self):
        # bind_all also captures keystrokes when focus is on a Button or Frame.
        # The user can recover focus using ACTIVATE WASD after editing a track.
        self.root.bind_all('<KeyPress>', self._key_down, add='+')
        self.root.bind_all('<KeyRelease>', self._key_up, add='+')
        self.root.bind('<FocusOut>', self._maybe_focus_lost)
        self.root.bind_all('<ButtonRelease-1>', lambda _e: self._clear_button_drive(), add='+')

    def activate_keyboard(self):
        """Re-arm WASD safely when user explicitly activates manual driving."""
        self._release_all_keys()
        self.drive_panel.focus_set()
        # A missed KeyRelease after an emergency stop should not lock out
        # keyboard driving forever. An explicit re-arm is allowed only when
        # no WASD physical key is currently down (Windows).
        still_down = False
        try:
            import sys
            if sys.platform == 'win32':
                import ctypes
                still_down = any(ctypes.windll.user32.GetAsyncKeyState(ord(k)) & 0x8000 for k in 'WASD')
        except (AttributeError, OSError):
            still_down = True  # cannot prove safe to re-arm
        if not still_down:
            self._blocked_drive_keys.clear()
        self.last_input_var.set('INPUT: RELEASE HELD KEYS before re-arming WASD' if still_down else
                                'INPUT: READY — hold W/A/S/D or press 1–4')
        self.log('WASD activated.' if not still_down else 'WASD still blocked until held keys released.')

    def _typing_focused(self):
        self._release_all_keys()
        self.last_input_var.set('INPUT: text field focused — click ACTIVATE WASD to drive')

    def _maybe_focus_lost(self, _event):
        if self._closed:
            return
        def check():
            self._focus_after = None
            # Only whole-window focus loss should stop driving. Switching from
            # an entry widget to the manual frame must not stop active movement.
            if not self._closed and self.root.focus_displayof() is None:
                self.emergency_stop(quiet=True)
                self.last_input_var.set('INPUT: window inactive — click ACTIVATE WASD')
        if self._focus_after is not None:
            self.root.after_cancel(self._focus_after)
        self._focus_after = self.root.after(90, check)

    def _typing(self, widget):
        return widget.winfo_class() in ('Entry', 'TEntry', 'Text', 'TCombobox', 'Spinbox')

    def _normalised_key(self, event):
        key = str(event.keysym or '').upper()
        if key.startswith('KP_') and key[3:] in ('1', '2', '3', '4'):
            return key[3:]
        if key in ('W', 'A', 'S', 'D', '1', '2', '3', '4', 'SPACE', 'ESCAPE'):
            return key
        # Some layouts report unusual keysyms; event.char can still be correct.
        char = str(event.char or '').upper()
        return char if char in ('W', 'A', 'S', 'D', '1', '2', '3', '4') else key

    def _key_down(self, event):
        key = self._normalised_key(event)
        if key not in ('W', 'A', 'S', 'D', '1', '2', '3', '4', 'SPACE', 'ESCAPE'):
            return
        if self.keyboard_test_active and key in ('W', 'A', 'S', 'D', '1', '2', '3', '4'):
            self.keyboard_test_active = False
            self.diagnosis.set('keyboard', 'PASS', f'Received physical key {key}; no motor command sent')
            self.last_input_var.set(f'INPUT DIAGNOSTIC: {key} received safely')
            return 'break'
        if self.diagnosis.is_running and key in ('W', 'A', 'S', 'D', '1', '2', '3', '4'):
            self.last_input_var.set(f'DIAGNOSTICS ACTIVE: {key} detected; driving suppressed')
            return 'break'
        # ESC remains a global emergency stop even while editing route text.
        # Space is reserved for typing spaces inside entries/text boxes.
        if key == 'ESCAPE':
            self.emergency_stop()
            return 'break'
        if self._typing(event.widget):
            self.last_input_var.set(f'INPUT: {key} ignored — text field focused; click ACTIVATE WASD')
            return
        self.last_input_var.set(f'INPUT: detected {key} ({event.widget.winfo_class()})')
        if key in ('W', 'A', 'S', 'D'):
            self._keyboard_pressed.add(key)
            if key in self._blocked_drive_keys:
                self._cancel_block_release(key)
                return 'break'
            # Windows/Tk can send KeyRelease immediately before the next
            # KeyPress while a key remains physically held. Cancel that
            # deferred release rather than briefly cutting motor power.
            self._cancel_pending_release(key)
            self._press(key, source='keyboard')
        elif key in ('1', '2', '3', '4'):
            self.set_gear(int(key))
        elif key in ('SPACE', 'ESCAPE'):
            self.emergency_stop()
        return 'break'

    def _key_up(self, event):
        key = self._normalised_key(event)
        # Tk on Windows generates fake release/press pairs during key repeat.
        # Do NOT clear physical-held state until the release is confirmed.
        if key in self._blocked_drive_keys:
            # Tk may synthesize a KeyRelease/KeyPress pair for Windows key repeat.
            # Deferring unblocking prevents a still-held key from defeating BRAKE.
            self._cancel_block_release(key)
            self._pending_block_releases[key] = self.root.after(
                self._release_debounce_ms, lambda k=key: self._confirm_block_release(k))
            return
        if key in ('W', 'A', 'S', 'D') and key in self._pressed_sources and 'keyboard' in self._pressed_sources[key]:
            # Real release is committed after a short grace period. Repeated
            # KeyPress events cancel it; real release still stops promptly.
            self._cancel_pending_release(key)
            self._pending_key_releases[key] = self.root.after(
                self._release_debounce_ms,
                lambda k=key: self._commit_key_release(k))

    def _cancel_pending_release(self, key):
        job = self._pending_key_releases.pop(key, None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass

    def _commit_key_release(self, key):
        self._pending_key_releases.pop(key, None)
        if self._physical_key_down(key) is True:
            # Synthetic release; the user is still holding the physical key.
            return
        self._physical_key_misses.pop(key, None)
        self._keyboard_pressed.discard(key)
        self._release(key, source='keyboard')

    def _cancel_block_release(self, key):
        job = self._pending_block_releases.pop(key, None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass

    def _confirm_block_release(self, key):
        self._pending_block_releases.pop(key, None)
        if self._physical_key_down(key) is True:
            # An emergency brake cannot be cancelled by Windows key repeat.
            return
        self._blocked_drive_keys.discard(key)
        self._keyboard_pressed.discard(key)

    def _release_all_keys(self):
        self._keyboard_pressed.clear()
        self._physical_key_misses.clear()
        for key in list(self._pending_key_releases):
            self._cancel_pending_release(key)
        for key in list(self._pending_block_releases):
            self._cancel_block_release(key)
        for sources in self._pressed_sources.values():
            sources.clear()
        self.pressed.clear()
        if not self.running and self.online:
            self._apply_release_brake()
        self._display_manual_command()

    def _display_manual_command(self):
        self.keys_var.set('HELD KEYS: ' + (' + '.join(sorted(self.pressed)) if self.pressed else 'none'))
        if not self.running:
            left, right = self._manual_wheels()
            suffix = ' (DEMO)' if self.demo else (' (DISCONNECTED)' if not self.online else '')
            self.command_var.set(f'L {left:+4d}   |   R {right:+4d}   |   GEAR {self.gear}{suffix}')

    def _press(self, key, source='api'):
        if self.diagnosis.is_running or self.keyboard_test_active:
            self.last_input_var.set(f'INPUT: {key} detected; driving suppressed during diagnostics')
            return
        if self.running:
            self.emergency_stop(quiet=True)
        if key not in self.pressed:
            self.last_input_var.set(f'INPUT: {key} DOWN — holding moves buggy when connected')
        if key in self._blocked_drive_keys:
            return
        self.brake_latched = False
        self.flight.record('INPUT', f'{key}_DOWN', source)
        self._pressed_sources[key].add(source)
        self.pressed.add(key)
        if self.online and not self.demo:
            left, right = self._manual_wheels()
            self.bridge.set_motor(left, right)
        self._display_manual_command()  # instant response, even between 80 ms refreshes

    def _release(self, key, source='api'):
        if source != 'keyboard' and key in self._blocked_drive_keys:
            self._blocked_drive_keys.discard(key)
        if source == 'keyboard':
            self._keyboard_pressed.discard(key)
        self._cancel_pending_release(key)
        self.flight.record('INPUT', f'{key}_UP', source)
        self._pressed_sources[key].discard(source)
        if not self._pressed_sources[key]:
            self.pressed.discard(key)
        if not self.pressed and not self.running:
            self._apply_release_brake()
        elif self.pressed and self.online and not self.demo:
            left, right = self._manual_wheels()
            self.bridge.set_motor(left, right)
        self._display_manual_command()

    def _apply_release_brake(self):
        # Never slowly coast to zero on key release: the buggy has no wheel encoder.
        self.brake_latched = True
        self.flight.record('SAFETY', 'KEY_RELEASE_BRAKE', 'Manual input released')
        self.applied_left = self.applied_right = 0.0
        if self.online and not self.demo:
            self.bridge.set_brake()
        self.drive_state_var.set('ACTIVE BRAKE / KEY RELEASE')

    def _clear_button_drive(self):
        # Mouse release does not clear keyboard-held inputs unless window lost focus.
        if not self.root.focus_displayof():
            self._release_all_keys()

    def _steering_changed(self, _value=None):
        self.steering_info_var.set(f'STEERING {self.steering_var.get()}%')
        self._display_manual_command()

    def _balance_changed(self, _value=None):
        pct = self.balance_var.get()
        self.balance_info_var.set(
            f'MOTOR BALANCE {pct:+d}% (favors {"RIGHT" if pct > 0 else "LEFT"})'
            if pct else 'MOTOR BALANCE 0% (equal)')
        self._display_manual_command()

    def set_gear(self, gear):
        self.gear = gear
        self._paint_gears()
        self.gear_info_var.set(self._gear_caption())
        self.last_input_var.set(f'INPUT: gear {gear} selected ({self._gear_caption()})')
        self._display_manual_command()
        self.log(f'Gear {gear} / PWM {GEARS[gear]}')
        if not self.running:
            self.preview_route(log_errors=False)

    def _paint_gears(self):
        for gear, button in self.gear_buttons.items():
            button.configure(bg=('#197f83' if gear == self.gear else '#24354b'))

    def scan(self):
        if self.demo_var.get():
            self.log('Turn off Demo mode to scan actual BLE devices.')
            return
        self.status_var.set('SCANNING...')
        self.bridge.scan()

    def toggle_connection(self):
        if self.online:
            self.emergency_stop(quiet=True)
            if self.demo:
                self.demo = False
                self.online = False
                self._connection_label(False)
                self.log('Demo disconnected.')
            else:
                self.status_var.set('DISCONNECTING...')
                self.bridge.disconnect()
            return
        if self.demo_var.get():
            self.demo = True
            self.online = True
            self.brake_latched = False
            self.telemetry_link_var.set('ARDUINO: DEMO / SIMULATED')
            self.telemetry_support = 'DEMO'
            self._connection_label(True)
            self.log('Demo mode started. Bluetooth and motors are NOT used.')
            self.root.after_idle(self.activate_keyboard)
            return
        choice = self.devices.get(self.device_var.get())
        if not choice:
            messagebox.showinfo('Choose a device', 'Click SCAN BLE and choose your HM-10 first.\n'
                                'It may appear as HMSoft if it was not actually renamed.')
            return
        self.status_var.set('CONNECTING...')
        self._last_tx_at = 0.0
        self._last_tx_ms = 0.0
        self.link_gatt = None
        self.link_notify_state = None
        self.telemetry_support = 'WAITING FOR ARDUINO'
        self.bridge.connect(choice, self.uuid_var.get())

    def _connection_label(self, connected):
        self.status_var.set('DEMO / NO MOTORS' if self.demo and connected else
                            ('CONNECTED / BLE' if connected else 'DISCONNECTED'))
        self.connect_btn.configure(text=('DISCONNECT' if connected else 'CONNECT'),
                                   bg=('#9e3d56' if connected else '#197f83'))

    def _events(self):
        while True:
            try:
                kind, payload = self.bridge.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'tx_frame':
                self._last_tx_at = payload['sent_at']
                self._last_tx_ms = payload['latency_ms']
                self._last_tx_payload = payload['frame']
                self.flight.record('BLE_TX', payload['frame'],
                                   f"write={payload['latency_ms']:.1f}ms; intent_age={payload['intent_age_ms']:.0f}ms")
                continue
            if kind == 'devices':
                self.devices = {}
                items = []
                for d in payload:
                    name = d.name or 'Unknown BLE'
                    label = f'{name}  —  {d.address}'
                    self.devices[label] = d
                    items.append(label)
                self.device_combo['values'] = items
                if items:
                    matching = next((x for x in items if any(n in x.lower() for n in
                                                ('cabbagelover', 'hmsoft', 'hm-10', 'hm10'))), items[0])
                    self.device_var.set(matching)
                self.log(f'Found {len(items)} BLE devices. Select your HM-10.')
                self.status_var.set('SELECT A DEVICE')
                if self.diag_phase == 'scan':
                    self._diagnostic_scan_finished(payload)
            elif kind == 'connected':
                self.demo = False
                self.online = True
                self.brake_latched = True  # don't move simply because BLE connected
                self.bridge.set_brake()
                self.last_feedback = None
                self.last_feedback_at = 0.0
                self.rx_count = 0
                self.tx_count = 0
                self.telemetry_link_var.set('ARDUINO: ' + self.telemetry_support)
                self._connection_label(True)
                self.flight.record('LINK', 'CONNECTED', str(payload))
                self.log(f'BLE connected: {payload}. FFE1 motor stream active.')
                if self.diag_phase == 'connect':
                    self.diagnosis.set('link', 'PASS', 'BLE link connected')
                    self._start_firmware_probe()
                else:
                    self.root.after_idle(self.activate_keyboard)
            elif kind in ('disconnected', 'lost'):
                if self.online and not self.demo:
                    self.emergency_stop(quiet=True)
                    self.online = False
                    self._connection_label(False)
                    self.telemetry_link_var.set('ARDUINO: DISCONNECTED')
                    self.flight.record('LINK', 'DISCONNECTED', str(payload))
                    self.log(str(payload))
                if self.diagnosis.started_at and not self.demo:
                    self.diagnosis.set('link', 'FAIL', str(payload))
                if self.diagnosis.is_running:
                    self._finish_diagnostics()
                self.link_gatt = None
                self.link_notify_state = None
            elif kind == 'telemetry_state':
                self.telemetry_support = str(payload)
                if self.online and not self.demo:
                    self.telemetry_link_var.set(f'ARDUINO: {payload}')
                if 'UNSUPPORTED' in str(payload) or 'FAILED' in str(payload):
                    self.log(f'Telemetry: {payload}. Commands may still work.')
            elif kind == 'telemetry':
                reading, arrived_at = payload
                self.flight.record('ARDUINO_RX', f'{reading.left_pwm:+d},{reading.right_pwm:+d}',
                                   f'{reading.state}; seq={reading.sequence}; rx_commands={reading.accepted_commands}')
                self.last_feedback = reading
                self.last_feedback_at = arrived_at
                self.rx_count += 1
                if self.diagnosis.is_running:
                    self.diagnosis.set('telemetry', 'PASS', f'Parsed Arduino telemetry, seq {reading.sequence:03d}; PWM commands, not RPM')
                self.telemetry_link_var.set('ARDUINO: LIVE REPLIES')
                self.telemetry_pwm_var.set(
                    f'APPLIED PWM: L {reading.left_pwm:+4d} / R {reading.right_pwm:+4d}')
                self.telemetry_state_var.set(f'DRIVER STATE: {reading.state} / SEQ {reading.sequence:03d}' +
                    (f' / RX CMD {reading.accepted_commands}' if reading.accepted_commands is not None else ''))
                # Telemetry is Arduino *command acknowledgement*, not wheel rotation.
                if self.online and not self.demo and not self.running and self.pressed and not self.brake_latched:
                    expected = self._manual_wheels()
                    received = (reading.left_pwm, reading.right_pwm)
                    if received != expected and time.monotonic() - self._feedback_warning_at > 3:
                        self._feedback_warning_at = time.monotonic()
                        self.log(f'WARNING: Arduino command {received} differs from requested {expected}. Check BLE UART.')
                if reading.state == 'WATCHDOG BRAKE' and self.online and not self.brake_latched:
                    self.log('SAFETY: Arduino watchdog braked. Release all keys before attempting to drive again.')
                    self.flight.record('SAFETY', 'ARDUINO_WATCHDOG', 'Motor packet stream interrupted')
                    self.emergency_stop(quiet=True)
            elif kind == 'tx_stats':
                self.tx_count = int(payload)
            elif kind == 'scan_started':
                if self.diag_phase == 'scan':
                    self.diagnosis.set('scan', 'PENDING', 'Scanning Windows BLE advertisements')
            elif kind == 'scan_failed':
                if self.diagnosis.is_running:
                    self.diagnosis.set('scan', 'FAIL', str(payload))
                    self.diagnosis.set('device', 'SKIP', 'BLE scanning failed')
                    self._finish_diagnostics()
            elif kind == 'link_progress':
                if self.diagnosis.is_running:
                    self.diagnosis.set('link', 'PENDING', str(payload))
            elif kind == 'connect_failed':
                if self.diagnosis.is_running:
                    stage, suggestion = interpret_error(str(payload))
                    self.diagnosis.set(stage if stage in ('link', 'gatt') else 'link', 'FAIL',
                                       f'{payload}. {suggestion}')
                    self._finish_diagnostics()
            elif kind == 'gatt_ok':
                self.link_gatt = payload
                if self.diagnosis.is_running:
                    self.diagnosis.set('gatt', 'PASS', f"Writable {payload['uuid']} ({payload['write_mode']})")
            elif kind == 'notify_ok':
                self.link_notify_state = 'PASS'
                if self.diagnosis.is_running:
                    self.diagnosis.set('notify', 'PASS', str(payload))
            elif kind == 'notify_failed':
                self.link_notify_state = 'WARN'
                if self.diagnosis.is_running:
                    self.diagnosis.set('notify', 'WARN', str(payload))
            elif kind == 'write_ok':
                if self.diagnosis.is_running:
                    self.diagnosis.set('write', 'PASS', 'BLE stack accepted outgoing GATT motor/brake writes; not proof of Arduino receipt')
            elif kind == 'write_failed':
                self.flight.record('BLE_ERROR', 'WRITE_FAILED', str(payload))
                if self.diagnosis.started_at:
                    self.diagnosis.set('write', 'FAIL', str(payload))
                    self._finish_diagnostics()
            elif kind == 'probe_sent':
                if self.diagnosis.is_running and int(payload) == 1:
                    self.diagnosis.set('firmware', 'PENDING', 'Sent safe Q handshake request (motors braked)')
            elif kind == 'probe_error':
                if self.diagnosis.is_running:
                    self.diagnosis.set('firmware', 'FAIL', str(payload))
                    self._finish_diagnostics()
            elif kind == 'firmware_reply':
                if self.diagnosis.is_running:
                    self.diagnosis.set('firmware', 'PASS', 'Arduino answered protocol H,13 — bidirectional UART confirmed')
            elif kind == 'unknown_reply':
                if self.diagnosis.is_running:
                    self.diagnosis.add('Unrecognized Arduino notification: ' + str(payload))
            elif kind == 'error':
                self.flight.record('ERROR', 'CONTROL_ERROR', str(payload))
                self.emergency_stop(quiet=True)
                self.log('ERROR: ' + str(payload))
                if not self.online:
                    self.status_var.set('BLE ERROR — SEE LOG')
            else:
                self.log(str(payload))

    def _config(self):
        # Build one new planner each time. No unbounded duplicate segments.
        planner = Planner(self.speed_var.get(), self.width_var.get(), self.gear)
        options = dict(length=float(self.length_var.get()), radius=float(self.radius_var.get()),
                       angle=float(self.angle_var.get()), legs=int(self.legs_var.get()),
                       laps=int(self.laps_var.get()), direction=self.turn_var.get(),
                       custom=self.custom_text.get('1.0', 'end'))
        parts = planner.build(self.shape_var.get(), **options)
        return planner, parts

    def preview_route(self, log_errors=True):
        if self.running:
            return
        try:
            planner, parts = self._config()
            self.route = parts
            self.full_speed = planner.max_speed
            self.wheelbase = planner.wheelbase
            duration = sum(p.duration for p in parts)
            self.stats_var.set(f'{len(parts)} steps     |     Approx. {duration:.1f} s     |     Gear {self.gear}')
            self.progress_var.set('PREVIEW READY — approximate dimensions')
            self.draw_preview()
        except (ValueError, OverflowError) as exc:
            self.route = []
            self.draw_preview()
            self.progress_var.set('INVALID TRACK PARAMETERS')
            if log_errors:
                messagebox.showerror('Track parameters', str(exc))

    def start_route(self):
        if self.diagnosis.is_running or self.keyboard_test_active:
            messagebox.showwarning('Diagnostics active', 'Finish the non-driving diagnostics before running a route.')
            return
        if not self.online:
            messagebox.showwarning('Not connected', 'Connect to your HM-10 or enable Demo mode first.')
            return
        if self.running:
            return
        self.preview_route()
        if not self.route:
            return
        if not self.demo:
            if not messagebox.askokcancel('Run automatic track?',
                    'The buggy will move automatically without obstacle detection.\n\n'
                    'Place it on a clear, level floor and keep it within sight.\n'
                    'Press STOP or Space at any time.\n\n'
                    'The dimensions are only approximate until you calibrate it.'):
                return
        for sources in self._pressed_sources.values():
            sources.clear()
        self.pressed.clear()
        self.brake_latched = False
        self.running = True
        self.route_index = 0
        self.segment_started = time.monotonic()
        self.log(f'Route started: {self.shape_var.get()}, {len(self.route)} steps.')

    def emergency_stop(self, quiet=False):
        for key in list(self._pending_key_releases):
            self._cancel_pending_release(key)
        for key in list(self._pending_block_releases):
            self._cancel_block_release(key)
        was_active = self.running or bool(self.pressed) or any((self.applied_left, self.applied_right))
        self.running = False
        self._blocked_drive_keys.update(self.pressed)
        for sources in self._pressed_sources.values():
            sources.clear()
        self.pressed.clear()
        self._keyboard_pressed.clear()
        self.brake_latched = True
        self.applied_left = 0.0
        self.applied_right = 0.0
        self.bridge.set_brake()
        self.flight.record('SAFETY', 'EMERGENCY_BRAKE', 'Space / Stop / focus / diagnostic')
        self._display_manual_command()
        self.drive_state_var.set('ACTIVE SHORT BRAKE / LATCHED')
        if was_active and not quiet:
            self.log('ACTIVE BRAKE requested. Verify both wheels stop; inspect right driver if not.')
        if was_active:
            self.progress_var.set('STOPPED')

    def _manual_wheels(self):
        return balance_wheels(*manual_wheels(self.pressed, self._manual_pwm(),
                                             self.steering_var.get()), self.balance_var.get())

    def _reconcile_physical_keys(self):
        """Windows: recover from dropped KeyRelease (otherwise continuous runaway).

        Key events remain the source of presses; OS polling can only *remove*
        held keyboard keys. Does not change mouse-button driving or Linux tests.
        """
        if not self._keyboard_pressed:
            return
        try:
            import sys
            if sys.platform != 'win32':
                return
            import ctypes
            user32 = ctypes.windll.user32
            for key in tuple(self._keyboard_pressed):
                if user32.GetAsyncKeyState(ord(key)) & 0x8000:
                    self._physical_key_misses.pop(key, None)
                else:
                    misses = self._physical_key_misses.get(key, 0) + 1
                    self._physical_key_misses[key] = misses
                    # Avoid a transient Windows key-state miss killing the drive.
                    # Three consecutive 80-ms misses still enforce safety.
                    if misses >= 3:
                        self._physical_key_misses.pop(key, None)
                        self._keyboard_pressed.discard(key)
                        self._cancel_pending_release(key)
                        if key in self.pressed:
                            self._release(key, source='keyboard')
        except (AttributeError, OSError):
            # Retain Tk release handling when native state isn't available.
            return

    def _tick(self):
        if self._closed:
            return
        now = time.monotonic()
        raw_dt = now - self._last_tick_at
        dt = max(0.0, min(0.15, raw_dt))
        self._last_tick_at = now
        # After a prolonged GUI stall, never resume a drive based on old keys
        # or advance an old automatic route unexpectedly. Physical re-arm needed.
        if raw_dt > 1.4 and self.online and not self.demo and (self.running or self.pressed):
            self.emergency_stop(quiet=True)
            self.flight.record('SAFETY', 'GUI_STALL_BRAKE', f'No UI refresh for {raw_dt:.2f}s')
            self.log(f'SAFETY STOP: UI stalled {raw_dt:.1f}s; release keys then reactivate WASD.')
        self._events()
        self._reconcile_physical_keys()
        self._diagnostic_clock(now)
        if self.diagnosis.started_at and not self.diagnosis.is_running and self.online and not self.demo:
            if self.diagnosis.checks['telemetry'].status in ('PASS', 'WARN'):
                if not (self.running or self.pressed) and self.last_feedback_at and now - self.last_feedback_at > 2.0:
                    self.diagnosis.set('telemetry', 'WARN', 'Arduino telemetry became stale (>2s) while connected')
                elif self.last_feedback_at and now - self.last_feedback_at <= 1.5 and self.diagnosis.checks['telemetry'].status == 'WARN':
                    self.diagnosis.set('telemetry', 'PASS', 'Arduino feedback resumed (PWM commands; not wheel RPM)')
        left, right = 0, 0
        if self.online:
            if self.running:
                if self.route_index < len(self.route):
                    segment = self.route[self.route_index]
                    elapsed = now - self.segment_started
                    if elapsed >= segment.duration:
                        self.route_index += 1
                        self.segment_started = now
                        if self.route_index >= len(self.route):
                            self.running = False
                            self.brake_latched = True
                            self.progress_var.set('ROUTE COMPLETE / ACTIVE BRAKE')
                            self.log('Route completed (timed estimate; no encoders).')
                        else:
                            segment = self.route[self.route_index]
                    if self.running:
                        left, right = segment.left, segment.right
                        self.applied_left, self.applied_right = float(left), float(right)
                        self.progress_var.set(f'RUNNING {self.route_index + 1}/{len(self.route)}: {segment.label}')
                        self.draw_preview()
            elif self.brake_latched:
                self.applied_left = self.applied_right = 0.0
            else:
                target_l, target_r = self._manual_wheels()
                # Manual controls send the requested gear PWM without a low-PWM ramp.
                # Some geared motors cannot overcome static friction at the old ramp's
                # initial ~60 PWM and appear to have a dead wheel (especially reverse).
                # Key-up separately latches active short brake.
                self.applied_left = float(target_l)
                self.applied_right = float(target_r)
                left, right = target_l, target_r
            if not self.demo:
                if self.brake_latched:
                    self.bridge.set_brake()
                else:
                    self.bridge.set_motor(left, right)
        else:
            self.applied_left = self.applied_right = 0.0
        if self.brake_latched and self.online:
            state = 'ACTIVE BRAKE / PRESS DRIVE KEY TO RELEASE'
        elif self.running:
            state = 'AUTOMATIC ROUTE / OPEN LOOP'
        elif (left, right) != (0, 0):
            state = f'MANUAL DRIVE / STEERING {self.steering_var.get()}%'
        else:
            state = 'COAST / IDLE'
        self.drive_state_var.set(state)
        suffix = ' (DEMO)' if self.demo else (' (DISCONNECTED)' if not self.online else '')
        self.command_var.set(f'L {left:+4d}   |   R {right:+4d}   |   GEAR {self.gear}{suffix}')
        self.telemetry_packets_var.set(f'BLE TX: {self.tx_count}     ARDUINO RX: {self.rx_count}')
        if self.demo and self.online:
            self.link_health_var.set('COMMAND LINK: DEMO ONLY / NO REAL BLE')
        elif self.online:
            age = now - self._last_tx_at if self._last_tx_at else None
            self.link_health_var.set('COMMAND LINK: ' +
                ('WAITING FOR FIRST WRITE' if age is None else
                 f"TX {age:.1f}s ago / last write {self._last_tx_ms:.0f}ms" +
                 ('  ⚠ TX STALE' if age > 0.6 else '')))
        else:
            self.link_health_var.set('COMMAND LINK: disconnected')
        if self.demo and self.online:
            self.telemetry_link_var.set('ARDUINO: DEMO / SIMULATED, NO BLE')
            self.telemetry_pwm_var.set(f'SIMULATED PWM: L {left:+4d} / R {right:+4d}')
            self.telemetry_state_var.set('DRIVER STATE: SIMULATED ONLY')
            self.telemetry_age_var.set('FEEDBACK AGE: DEMO')
        elif self.online and self.last_feedback:
            age = max(0.0, now - self.last_feedback_at)
            if self.running or self.pressed:
                self.telemetry_pwm_var.set('ARDUINO PWM: paused while driving; see commanded values above')
                self.telemetry_age_var.set(f'LAST IDLE FEEDBACK: {age:.1f}s ago')
            else:
                self.telemetry_pwm_var.set(
                    f'LAST ARDUINO PWM: L {self.last_feedback.left_pwm:+4d} / '
                    f'R {self.last_feedback.right_pwm:+4d}')
                self.telemetry_age_var.set(f'FEEDBACK AGE: {age:.1f}s')
            self.telemetry_link_var.set('ARDUINO: RX TELEMETRY PAUSED WHILE DRIVING'
                    if (self.running or self.pressed) else
                    ('ARDUINO: LIVE REPLIES' if age < 1.5 else 'ARDUINO: FEEDBACK STALE (>1.5s)'))
        elif self.online:
            self.telemetry_age_var.set('FEEDBACK AGE: waiting')
        self._redraw_telemetry_bars()
        if self.diagnostic_window is not None:
            self.diagnostic_window.refresh()
        self._tick_after = self.root.after(80, self._tick)

    def _redraw_telemetry_bars(self):
        if not hasattr(self, 'telemetry_bars'):
            return
        c = self.telemetry_bars
        c.delete('all')
        w = max(150, c.winfo_width())
        if self.demo and self.online:
            motors = (round(self.applied_left), round(self.applied_right))
            source = 'SIM'
        elif self.online and self.last_feedback and time.monotonic() - self.last_feedback_at < 1.5:
            motors = (self.last_feedback.left_pwm, self.last_feedback.right_pwm)
            source = 'ACK'
        else:
            motors = (0, 0)
            source = '--'
        for i, (side, power) in enumerate(zip(('L', 'R'), motors)):
            y = 12 + i * 21
            x0, x1 = 62, w - 75
            middle = (x0 + x1) / 2
            c.create_text(9, y, text=side, anchor='w', fill=MUTED,
                          font=('Consolas', 10, 'bold'))
            c.create_rectangle(x0, y - 6, x1, y + 6, outline=BORDER, fill='#16253a')
            c.create_line(middle, y - 8, middle, y + 8, fill=MUTED)
            extent = (x1 - x0) / 2 * min(1, abs(power) / 255)
            if extent:
                c.create_rectangle(middle if power >= 0 else middle - extent,
                                   y - 5, middle + extent if power >= 0 else middle,
                                   y + 5, outline='', fill=GREEN if power >= 0 else AMBER)
            c.create_text(w - 8, y, text=f'{power:+4d} {source}', anchor='e',
                          fill=TEXT, font=('Consolas', 8))

    def draw_preview(self):
        if not hasattr(self, 'preview'):
            return
        canvas = self.preview
        canvas.delete('all')
        w = max(100, canvas.winfo_width())
        h = max(100, canvas.winfo_height())
        for x in range(0, w + 1, 28):
            canvas.create_line(x, 0, x, h, fill='#1b2941', width=1)
        for y in range(0, h + 1, 28):
            canvas.create_line(0, y, w, y, fill='#1b2941', width=1)
        if not self.route:
            canvas.create_text(w / 2, h / 2, text='Choose a track and press PREVIEW',
                               fill=MUTED, font=('Segoe UI', 13))
            return
        points = sample_path(self.route, self.full_speed, self.wheelbase)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dx = max(maxx - minx, 10)
        dy = max(maxy - miny, 10)
        padding = 44
        scale = min((w - 2 * padding) / dx, (h - 2 * padding) / dy, 5)
        midx = (minx + maxx) / 2
        midy = (miny + maxy) / 2
        def pos(x, y):
            return (w / 2 + (x - midx) * scale, h / 2 - (y - midy) * scale)
        flat = [v for pt in points for v in pos(*pt)]
        if len(flat) >= 4:
            canvas.create_line(*flat, fill=CYAN, width=3, smooth=False)
        sx, sy = pos(*points[0])
        ex, ey = pos(*points[-1])
        canvas.create_oval(sx-6, sy-6, sx+6, sy+6, fill=GREEN, outline='')
        canvas.create_text(sx+10, sy-12, text='START', anchor='w',
                           fill=GREEN, font=('Segoe UI', 9, 'bold'))
        canvas.create_oval(ex-5, ey-5, ex+5, ey+5, fill=AMBER, outline='')
        if self.running and self.route_index < len(self.route):
            elapsed = time.monotonic() - self.segment_started
            x, y, heading = route_pose(self.route, self.route_index, elapsed,
                                       self.full_speed, self.wheelbase)
            mx, my = pos(x, y)
            canvas.create_oval(mx-8, my-8, mx+8, my+8, fill=AMBER, outline=TEXT, width=1)
            canvas.create_line(mx, my, mx+15*math.cos(heading),
                               my-15*math.sin(heading), fill=TEXT, width=3)
        canvas.create_text(12, h-12, text=f'Approx. bounds: {maxx-minx:.0f} × {maxy-miny:.0f} cm',
                           fill=MUTED, anchor='sw', font=('Segoe UI', 9))

    def _shutdown(self):
        if self._closed:
            return
        self._closed = True
        self.emergency_stop(quiet=True)
        for after_id in (self._tick_after, self._preview_after, self._focus_after):
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
        self.bridge.close()

    def _quit(self):
        self._shutdown()
        self.root.after(350, self.root.destroy)


def main():
    import sys
    root = tk.Tk()
    app = BuggyApp(root)
    if '--demo' in sys.argv:
        def enable_demo():
            app.demo_var.set(True)
            app.toggle_connection()
        root.after(100, enable_demo)
    root.mainloop()


if __name__ == '__main__':
    main()
