"""Non-modal live diagnostics console; no secondary BLE operations in the Tk thread."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from diagnostics import STEPS

BG, CARD, BORDER = '#0b1020', '#141d30', '#2c3850'
TEXT, MUTED, GREEN, AMBER, RED, CYAN = '#f1f5ff', '#99abc7', '#4ddd9c', '#f5c26b', '#ff667e', '#55d9e9'
STATUS_COLOR = {'PASS': GREEN, 'WARN': AMBER, 'FAIL': RED, 'PENDING': MUTED,
                'MANUAL': AMBER, 'SKIP': MUTED}


class DiagnosticWindow:
    def __init__(self, app):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title('BUGGY / Connection & Hardware Diagnostics v1.6.3')
        self.top.geometry('1030x760')
        self.top.minsize(860, 670)
        self.top.configure(bg=BG)
        self.top.protocol('WM_DELETE_WINDOW', self.close)
        tk.Label(self.top, text='DIAGNOSTICS LAB', bg=BG, fg=CYAN,
                 font=('Segoe UI', 21, 'bold')).pack(anchor='w', padx=20, pady=(14, 2))
        tk.Label(self.top, text='Non-driving BLE checks · Arduino firmware handshake · actionable repair guide',
                 bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(anchor='w', padx=20)
        actions = tk.Frame(self.top, bg=BG)
        actions.pack(fill='x', padx=20, pady=(12, 12))
        for title, cmd, color in [
            ('RUN FULL DIAGNOSIS', app.run_diagnostics, '#177e79'),
            ('TEST KEYBOARD', app.start_keyboard_diagnosis, '#305c91'),
            ('COPY REPORT', self.copy_report, '#325373'),
            ('SAVE REPORT', self.save_report, '#325373'),
            ('WIRING CHECKLIST', self.wiring_checklist, '#6b528f'),
        ]:
            tk.Button(actions, text=title, command=cmd, bg=color, fg='white',
                      activebackground=CYAN, relief='flat', padx=12, pady=9,
                      font=('Segoe UI', 9, 'bold'), cursor='hand2').pack(side='left', padx=(0, 9))
        self.summary_var = tk.StringVar(value='No diagnostics run yet')
        tk.Label(self.top, textvariable=self.summary_var, bg=BG, fg=TEXT,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=20, pady=(0, 8))
        holder = tk.Frame(self.top, bg=BG)
        holder.pack(fill='both', expand=True, padx=20)
        left_outer = tk.Frame(holder, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        left_outer.pack(side='left', fill='both', expand=True, padx=(0, 12))
        left_scroll = tk.Scrollbar(left_outer, orient='vertical', width=12)
        left_scroll.pack(side='right', fill='y')
        left_canvas = tk.Canvas(left_outer, bg=CARD, highlightthickness=0,
                                yscrollcommand=left_scroll.set)
        left_canvas.pack(side='left', fill='both', expand=True)
        left_scroll.config(command=left_canvas.yview)
        left = tk.Frame(left_canvas, bg=CARD)
        left_id = left_canvas.create_window((0, 0), window=left, anchor='nw')
        left.bind('<Configure>', lambda _e: left_canvas.configure(scrollregion=left_canvas.bbox('all')))
        left_canvas.bind('<Configure>', lambda e: left_canvas.itemconfigure(left_id, width=e.width))
        right = tk.Frame(holder, bg=CARD, highlightbackground=BORDER, highlightthickness=1, width=390)
        right.pack(side='left', fill='both')
        right.pack_propagate(False)
        tk.Label(left, text='LAYER-BY-LAYER RESULTS', bg=CARD, fg=TEXT,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=15, pady=(14, 9))
        self.status_vars = {}
        self.detail_vars = {}
        for key, name in STEPS:
            r = tk.Frame(left, bg=CARD)
            r.pack(fill='x', padx=14, pady=5)
            tk.Label(r, text=name, bg=CARD, fg=TEXT, font=('Segoe UI', 10),
                     anchor='w').pack(side='left')
            state = tk.StringVar(value='PENDING')
            tag = tk.Label(r, textvariable=state, bg=CARD, fg=MUTED,
                           font=('Consolas', 9, 'bold'), width=9, anchor='e')
            tag.pack(side='right')
            self.status_vars[key] = (state, tag)
            detail = tk.StringVar(value='Not checked yet')
            tk.Label(left, textvariable=detail, bg=CARD, fg=MUTED,
                     font=('Segoe UI', 8), anchor='w', justify='left', wraplength=510).pack(
                         fill='x', padx=14, pady=(0, 5))
            self.detail_vars[key] = detail
        tk.Label(right, text='SUGGESTED NEXT FIX', bg=CARD, fg=CYAN,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=14, pady=(14, 8))
        self.advice_var = tk.StringVar(value='Click RUN FULL DIAGNOSIS to start.')
        tk.Label(right, textvariable=self.advice_var, bg=CARD, fg=TEXT,
                 wraplength=352, justify='left', font=('Segoe UI', 10)).pack(fill='x', padx=14)
        tk.Label(right, text='EVENT TRACE (LATEST AT BOTTOM)', bg=CARD, fg=CYAN,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=14, pady=(20, 7))
        trace = tk.Frame(right, bg=CARD)
        trace.pack(fill='both', expand=True, padx=14, pady=(0, 14))
        self.trace = tk.Text(trace, bg='#10182a', fg=MUTED, insertbackground=TEXT,
                             font=('Consolas', 9), wrap='word', state='disabled', relief='flat')
        scr = tk.Scrollbar(trace, command=self.trace.yview)
        scr.pack(side='right', fill='y')
        self.trace.configure(yscrollcommand=scr.set)
        self.trace.pack(side='left', fill='both', expand=True)
        safety = ('MOTOR CHECK: software cannot measure wheel spin or battery voltage. '
                  'Lift the wheels and run MotorTest.ino. Verify VM battery power, 5V VCC, '
                  'common GND, D4→STBY and crossed HM-10 TX/RX wiring.')
        tk.Label(self.top, text=safety, bg=BG, fg=AMBER, wraplength=960,
                 justify='left', font=('Segoe UI', 9)).pack(anchor='w', padx=20, pady=(11, 16))
        self._trace_count = 0
        self.refresh()

    def refresh(self):
        model = self.app.diagnosis
        for key, _ in STEPS:
            c = model.checks[key]
            state, label = self.status_vars[key]
            state.set(c.status)
            label.configure(fg=STATUS_COLOR[c.status])
            self.detail_vars[key].set(c.detail)
        self.summary_var.set(('RUNNING — ' if model.is_running else '') + model.summary())
        self.advice_var.set(model.advice())
        if self._trace_count > len(model.messages):
            self._trace_count = 0
            self.trace.configure(state='normal')
            self.trace.delete('1.0', 'end')
            self.trace.configure(state='disabled')
        new = model.messages[self._trace_count:]
        if new:
            self.trace.configure(state='normal')
            for line in new:
                self.trace.insert('end', line + '\n')
            self.trace.see('end')
            self.trace.configure(state='disabled')
        self._trace_count = len(model.messages)

    def copy_report(self):
        self.top.clipboard_clear()
        self.top.clipboard_append(self.app.diagnosis.export_text())
        self.app.log('Diagnostic report copied to clipboard.')

    def save_report(self):
        path = filedialog.asksaveasfilename(parent=self.top, title='Save Buggy Diagnostic Report',
                                            defaultextension='.txt',
                                            initialfile='buggy-diagnostics.txt',
                                            filetypes=[('Text files', '*.txt')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as fp:
                fp.write(self.app.diagnosis.export_text())
        except OSError as exc:
            messagebox.showerror('Unable to save report', str(exc), parent=self.top)
            return
        self.app.log('Diagnostic report saved locally.')

    def wiring_checklist(self):
        dialog = tk.Toplevel(self.top)
        dialog.title('Manual wiring checklist — user observations')
        dialog.geometry('620x465')
        dialog.configure(bg=BG)
        dialog.transient(self.top)
        tk.Label(dialog, text='CHECK WITH POWER OFF (EXCEPT METER TESTS)', bg=BG, fg=AMBER,
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=20, pady=(16, 12))
        checks = [
            'Battery + through switch to VM; battery - to GND',
            'Arduino 5V to driver VCC (NOT VM)',
            'Arduino, battery and motor driver share GND',
            'Arduino D4 to STBY; D5/D6 PWM wires in place',
            'HM-10 TXD to Uno D2; Uno D3 to RXD via 3.3V divider',
            'Motor A to AO1/AO2; Motor B to BO1/BO2',
            'MotorTest.ino physically spun both wheels (wheels raised)',
        ]
        states = [tk.BooleanVar(value=False) for _ in checks]
        for text, variable in zip(checks, states):
            tk.Checkbutton(dialog, text=text, variable=variable, bg=BG, fg=TEXT,
                           selectcolor=CARD, activebackground=BG, activeforeground=TEXT,
                           justify='left', font=('Segoe UI', 10)).pack(anchor='w', padx=18, pady=5)
        tk.Label(dialog, text='These boxes are your observations — NOT sensor measurements.',
                 bg=BG, fg=AMBER, font=('Segoe UI', 9)).pack(anchor='w', padx=20, pady=8)
        def record():
            completed = [text for text, variable in zip(checks, states) if variable.get()]
            self.app.diagnosis.set('hardware', 'MANUAL',
                                   f'{len(completed)}/{len(checks)} items manually confirmed by user — not automatically verified')
            for item in completed:
                self.app.diagnosis.add('USER CONFIRMED: ' + item)
            dialog.destroy()
        tk.Button(dialog, text='RECORD USER CHECKS', command=record, bg='#177e79',
                  fg='white', relief='flat', padx=14, pady=9,
                  font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=20, pady=(4, 12))

    def close(self):
        self.app.diagnostic_window = None
        self.top.destroy()
