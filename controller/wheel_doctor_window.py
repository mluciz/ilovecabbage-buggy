"""Guided, opt-in wheel bench diagnostics.

Only a deliberately clicked short pulse may move a wheel. Results are human
observations; there is no encoder feedback and no automatic drive sequence.
"""
from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from wheel_doctor import STEPS, RESULTS, audit_sources, diagnose

BG = "#0b1020"
CARD = "#141d30"
DEEP = "#10182a"
EDGE = "#30435a"
TEXT = "#f1f5ff"
MUTED = "#a5b8d0"
TEAL = "#55d9e9"
GREEN = "#4ddd9c"
AMBER = "#f5c26b"
RED = "#ff667e"


class WheelDoctorWindow:
    def __init__(self, app):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title("BUGGY / WHEEL DOCTOR — motor fault isolation")
        self.top.geometry("1050x800")
        self.top.minsize(780, 620)
        self.top.configure(bg=BG)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.observations = {step: tk.StringVar(value="NOT TESTED") for step, _, _, _ in STEPS}
        self.wheels_raised = tk.BooleanVar(value=False)
        self.cutoff_ready = tk.BooleanVar(value=False)
        self.summary = tk.StringVar(value="Start with PIN AUDIT. Physical wiring is unverified.")
        self.version = tk.StringVar(value="Firmware version: not verified")
        self._last_probe = ""
        self.pulse_buttons = []

        header = tk.Frame(self.top, bg=BG)
        header.pack(fill="x", padx=22, pady=(15, 7))
        tk.Label(header, text="WHEEL DOCTOR", bg=BG, fg=TEAL,
                 font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(header, text="FIELD LAB  /  NO AUTO-DRIVE", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10, "bold")).pack(side="right", pady=8)
        tk.Label(self.top, text="Find why a wheel won't turn: source pins → Bluetooth → Arduino → driver → physical wheel.",
                 bg=BG, fg=TEXT, font=("Segoe UI", 11)).pack(anchor="w", padx=22)

        actions = tk.Frame(self.top, bg=BG)
        actions.pack(fill="x", padx=22, pady=(13, 7))
        for label, callback, tint in [
            ("1  SOURCE PIN AUDIT", self.pin_audit, "#305c91"),
            ("2  PROBE FIRMWARE", self.probe_version, "#305c91"),
            ("3  DIAGNOSE RESULTS", self.analyze, "#177e79"),
            ("COPY REPORT", self.copy_report, "#38526f"),
            ("SAVE REPORT", self.save_report, "#38526f"),
        ]:
            tk.Button(actions, text=label, command=callback, bg=tint, fg="white",
                      activebackground=TEAL, activeforeground=DEEP, relief="flat",
                      padx=12, pady=9, font=("Segoe UI", 9, "bold"),
                      cursor="hand2").pack(side="left", padx=(0, 7))

        self._status_bar = tk.Label(self.top, textvariable=self.summary, bg=CARD,
                                    fg=AMBER, anchor="w", padx=12, pady=9,
                                    font=("Segoe UI", 10, "bold"))
        self._status_bar.pack(fill="x", padx=22, pady=(5, 6))
        tk.Label(self.top, textvariable=self.version, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=22)

        safety = tk.Frame(self.top, bg=CARD, highlightbackground=EDGE, highlightthickness=1)
        safety.pack(fill="x", padx=22, pady=(10, 12))
        tk.Label(safety, text="BEFORE ANY MOTOR PULSE", bg=CARD, fg=AMBER,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(9, 1))
        for var, label in [
            (self.wheels_raised, "I personally lifted BOTH wheels fully off the surface, with nothing near them."),
            (self.cutoff_ready, "I can immediately switch OFF motor-battery power if anything behaves unexpectedly."),
        ]:
            tk.Checkbutton(safety, text=label, variable=var, bg=CARD, fg=TEXT,
                           selectcolor=DEEP, activebackground=CARD,
                           activeforeground=TEXT, font=("Segoe UI", 9),
                           command=self.refresh).pack(anchor="w", padx=10, pady=2)
        tk.Label(safety, text="Pulses are opt-in, 450 ms maximum, PWM 150, individually selected; never automatic. "
                 "App pulses require compatible V,165 firmware. STOP/Escape also requests X latch; a battery switch is essential.",
                 bg=CARD, fg=AMBER, wraplength=950, justify="left",
                 font=("Segoe UI", 9)).pack(fill="x", anchor="w", padx=12, pady=(2, 10))

        body = tk.Frame(self.top, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 10))
        stage = tk.Frame(body, bg=CARD, highlightbackground=EDGE, highlightthickness=1)
        stage.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(stage, text="SIX ISOLATED WHEEL CHECKS", bg=CARD, fg=TEAL,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 3))
        tk.Label(stage, text="After each pulse, choose what you actually observed. "
                 "Select FAILED TO BRAKE if a wheel kept moving.",
                 bg=CARD, fg=MUTED, wraplength=480, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 10))
        for n, (step, title, left, right) in enumerate(STEPS, start=1):
            row = tk.Frame(stage, bg=DEEP)
            row.pack(fill="x", padx=10, pady=4)
            tk.Label(row, text=f"{n:02d}  {title}", bg=DEEP, fg=TEXT,
                     width=19, anchor="w", font=("Consolas", 10, "bold")
                     ).pack(side="left", padx=(9, 1), pady=8)
            btn = tk.Button(row, text="TEST 0.45s", bg="#27766e", fg="white",
                            disabledforeground=MUTED, relief="flat",
                            command=lambda a=left, b=right, t=title: self.pulse(a, b, t),
                            font=("Segoe UI", 9, "bold"), padx=8, pady=5)
            btn.pack(side="left", padx=4)
            self.pulse_buttons.append(btn)
            combo = ttk.Combobox(row, textvariable=self.observations[step],
                                 values=list(RESULTS), state="readonly", width=18)
            combo.pack(side="left", padx=5)
            combo.bind("<<ComboboxSelected>>", lambda _e: self.analyze())
        tk.Label(stage, text="No app pulse? Use Arduino/ MotorTest.ino via USB, send T at 9600 baud "
                 "with wheels raised. Record each direction after the test.",
                 bg=CARD, fg=MUTED, wraplength=490, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 10))

        report_box = tk.Frame(body, bg=CARD, highlightbackground=EDGE, highlightthickness=1, width=410)
        report_box.pack(side="left", fill="both")
        report_box.pack_propagate(False)
        tk.Label(report_box, text="WHAT THE EVIDENCE SAYS", bg=CARD, fg=TEAL,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 8))
        textbox = tk.Frame(report_box, bg=CARD)
        textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        scroll = tk.Scrollbar(textbox)
        scroll.pack(side="right", fill="y")
        self.report = tk.Text(textbox, bg=DEEP, fg=TEXT, insertbackground=TEXT,
                              font=("Consolas", 9), relief="flat", wrap="word",
                              yscrollcommand=scroll.set)
        self.report.pack(fill="both", expand=True)
        scroll.config(command=self.report.yview)
        self.analyze()
        self.refresh()

    def pin_audit(self):
        ok, lines = audit_sources()
        self._show_report("\n".join(lines))
        self.summary.set("PIN AUDIT: matching source declarations (wires not verified)" if ok
                         else "PIN AUDIT FAILED — correct source inconsistency before flashing")
        self._status_bar.configure(fg=GREEN if ok else RED)

    def probe_version(self):
        if not self.app.online or self.app.demo:
            self.summary.set("Connect the real buggy first; demo cannot verify a firmware version.")
            return
        self.app.bridge.probe_version()
        self.summary.set("Sent non-driving V query. Awaiting V,165 from Arduino over HM-10.")

    def pulse(self, left, right, label):
        if not self.wheels_raised.get() or not self.cutoff_ready.get():
            messagebox.showwarning("Safety confirmation needed",
                "Lift both wheels AND confirm that you can physically disconnect motor power.",
                parent=self.top)
            return
        if not self.app.online or self.app.demo:
            messagebox.showwarning("Real BLE connection required",
                "App motor pulses are unavailable offline or in Demo mode. "
                "You can still audit the pins and record standalone MotorTest results.",
                parent=self.top)
            return
        if self.app.firmware_version != 165:
            messagebox.showwarning("Firmware not authenticated",
                "This pulse requires V,165 from the candidate BuggyController firmware. "
                "Probe the version first. Older software may not latch emergency stops.",
                parent=self.top)
            return
        if not messagebox.askokcancel("Confirm isolated wheel test",
                f"{label}: command L {left:+d} / R {right:+d} for at most 450 ms.\n\n"
                "Both wheels must be lifted. Motor switch within immediate reach. "
                "Press Cancel if any wire is loose or a wheel moves unexpectedly.",
                parent=self.top):
            return
        if self.app.start_wheel_probe(left, right):
            self.summary.set(f"TEST SENT: {label}. Watch the wheel; record what you SEE, not the PWM.")
            self._status_bar.configure(fg=AMBER)
            self.refresh()

    def analyze(self):
        evidence = self.app.last_feedback
        last = (f"L {evidence.left_pwm}, R {evidence.right_pwm}, {evidence.state}"
                if evidence is not None else None)
        content = diagnose({key: var.get() for key, var in self.observations.items()},
                           connected=self.app.online and not self.app.demo,
                           firmware_confirmed=self.app.firmware_version == 165,
                           rx_count=self.app.rx_count, last_telemetry=last)
        self._show_report(content)
        total = sum(var.get() != "NOT TESTED" for var in self.observations.values())
        if any(var.get() == "FAILED TO BRAKE" for var in self.observations.values()):
            self.summary.set("UNSAFE BRAKING — CUT MOTOR BATTERY; stop testing.")
            self._status_bar.configure(fg=RED)
            self.app.emergency_stop(quiet=True)
        else:
            self.summary.set(f"{total}/6 actual wheel observations recorded · "
                             "no RPM sensor; unknown results are not passes")
            self._status_bar.configure(fg=AMBER)
        return content

    def _show_report(self, text):
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("1.0", text)
        self.report.configure(state="disabled")

    def _report_text(self):
        return f"Exported: {datetime.now().astimezone().isoformat()}\n" + self.report.get("1.0", "end")

    def copy_report(self):
        self.top.clipboard_clear()
        self.top.clipboard_append(self._report_text())
        self.summary.set("Report copied — physical observations are self-reported.")

    def save_report(self):
        path = filedialog.asksaveasfilename(
            parent=self.top, defaultextension=".txt",
            initialfile="buggy-wheel-doctor.txt",
            filetypes=[("Text", "*.txt")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(self._report_text())
            except OSError as exc:
                messagebox.showerror("Cannot save", str(exc), parent=self.top)

    def refresh(self):
        if not self.top.winfo_exists():
            return
        is_ready = (self.app.online and not self.app.demo and
                    self.app.firmware_version == 165 and
                    self.wheels_raised.get() and self.cutoff_ready.get() and
                    not getattr(self.app, "wheel_probe_active", False) and
                    not any(v.get() == "FAILED TO BRAKE" for v in self.observations.values()))
        for btn in self.pulse_buttons:
            btn.config(state="normal" if is_ready else "disabled")
        self.version.set("Firmware: " +
            ("V,165 verified over BLE / test protocol available" if self.app.firmware_version == 165
             else "NOT VERIFIED — use PROBE FIRMWARE (needs newest sketch)"))

    def close(self):
        if getattr(self.app, "wheel_probe_active", False):
            self.app.emergency_stop(quiet=True)
        self.app.wheel_doctor_window = None
        self.top.destroy()
