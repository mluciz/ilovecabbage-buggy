"""A no-motor Power Path diagnostic studio for Uno/Arduino HM-10 battery issues."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from power_path import UNKNOWN, POWER, METER, REGULATOR, explain_power_failure

BG = '#08111e'
CARD = '#132238'
DEPTH = '#0c192b'
TEXT = '#edf6ff'
MUTED = '#9bb3c9'
TEAL = '#57e7cc'
AMBER = '#f2c17a'


class PowerPathWindow:
    def __init__(self, app):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title('CABBAGE / Power Path Lab — battery versus USB')
        self.top.geometry('1040x720')
        self.top.minsize(800, 600)
        self.top.configure(bg=BG)
        self.top.protocol('WM_DELETE_WINDOW', self.close)
        self.observations = {
            "usb_ble": tk.StringVar(value=UNKNOWN),
            "battery_ble": tk.StringVar(value=UNKNOWN),
            "battery_uno_led": tk.StringVar(value=UNKNOWN),
            "meter_3v3": tk.StringVar(value=UNKNOWN),
            "module_type": tk.StringVar(value=UNKNOWN),
            "common_ground": tk.StringVar(value=UNKNOWN),
        }

        heading = tk.Frame(self.top, bg=BG)
        heading.pack(fill='x', padx=21, pady=(15, 10))
        tk.Label(heading, text='POWER PATH LAB', bg=BG, fg=TEAL,
                 font=('Segoe UI', 22, 'bold')).pack(side='left')
        tk.Label(heading, text='NO MOTOR COMMANDS / SELF-REPORTED OBSERVATIONS',
                 bg=BG, fg=AMBER, font=('Segoe UI', 9, 'bold')).pack(side='right', pady=11)
        tk.Label(self.top,
                 text='Why does the HM-10 light up on laptop USB but disappear when the Uno runs from batteries?',
                 bg=BG, fg=TEXT, font=('Segoe UI', 11)).pack(anchor='w', padx=22, pady=(0, 13))
        body = tk.Frame(self.top, bg=BG)
        body.pack(fill='both', expand=True, padx=22, pady=(0, 12))
        form = tk.Frame(body, bg=CARD, width=430, highlightbackground='#30455b',
                        highlightthickness=1)
        form.pack(side='left', fill='both', padx=(0, 10))
        form.pack_propagate(False)
        tk.Label(form, text='OBSERVE / DO NOT GUESS', fg=TEAL, bg=CARD,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=14, pady=(16, 8))
        widgets = (
            ('usb_ble', 'HM-10 BLE advertising or power indicator on USB', POWER),
            ('battery_ble', 'Same indicator or advertising on battery only', POWER),
            ('battery_uno_led', 'Arduino Uno power LED with battery only', POWER),
            ('meter_3v3', '3.3V supply measured with a multimeter', METER),
            ('module_type', 'Your HM-10 VCC breakout hardware', REGULATOR),
            ('common_ground', 'Uno, HM-10 and driver share GND', POWER),
        )
        for key, label, choices in widgets:
            tk.Label(form, text=label, fg=TEXT, bg=CARD,
                     font=('Segoe UI', 9, 'bold'), wraplength=395,
                     justify='left').pack(anchor='w', padx=14, pady=(6, 3))
            combo = ttk.Combobox(form, values=choices, textvariable=self.observations[key],
                                 state='readonly', width=40, style='Dark.TCombobox')
            combo.pack(fill='x', padx=14, pady=(0, 3))
            combo.bind('<<ComboboxSelected>>', lambda _e: self.refresh())
        buttons = tk.Frame(form, bg=CARD)
        buttons.pack(fill='x', padx=12, pady=(17, 10))
        for label, fn in (('ANALYSE', self.refresh),
                          ('COPY', self.copy_report), ('SAVE', self.save_report)):
            tk.Button(buttons, text=label, command=fn, fg='white',
                      bg='#20776d' if label=='ANALYSE' else '#305073',
                      relief='flat', padx=13, pady=10,
                      font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 7))
        tk.Label(form, text='Always switch motor battery OFF before moving wires. '
                 'Measure a live rail only if you can do it safely.',
                 bg=CARD, fg=AMBER, font=('Segoe UI', 9), wraplength=400,
                 justify='left').pack(anchor='w', padx=14, pady=(3, 8))

        right = tk.Frame(body, bg=CARD, highlightbackground='#30455b',
                         highlightthickness=1)
        right.pack(side='left', fill='both', expand=True)
        tk.Label(right, text='DIAGNOSTIC RECOMMENDATIONS', bg=CARD, fg=TEAL,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=13, pady=(16, 8))
        wrapper = tk.Frame(right, bg=DEPTH)
        wrapper.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        scroll = tk.Scrollbar(wrapper)
        scroll.pack(side='right', fill='y')
        self.report = tk.Text(wrapper, bg=DEPTH, fg=TEXT, insertbackground=TEXT,
                              font=('Consolas', 9), wrap='word', padx=10, pady=9,
                              relief='flat', yscrollcommand=scroll.set)
        self.report.pack(fill='both', expand=True)
        scroll.configure(command=self.report.yview)
        self.refresh()

    def refresh(self):
        txt = explain_power_failure({k: v.get() for k, v in self.observations.items()})
        self.report.configure(state='normal')
        self.report.delete('1.0', 'end')
        self.report.insert('1.0', txt)
        self.report.configure(state='disabled')
        return txt

    def copy_report(self):
        text = self.refresh()
        self.top.clipboard_clear()
        self.top.clipboard_append(text)

    def save_report(self):
        filename = filedialog.asksaveasfilename(
            parent=self.top, defaultextension='.txt', initialfile='cabbage-power-path.txt',
            filetypes=[('Text report', '*.txt')])
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as out:
                    out.write(self.refresh())
            except OSError as exc:
                messagebox.showerror('Could not save report', str(exc), parent=self.top)

    def close(self):
        self.app.power_path_window = None
        self.top.destroy()
