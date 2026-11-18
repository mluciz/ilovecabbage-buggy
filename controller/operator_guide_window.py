"""Searchable in-app field manual; contains no motor commands."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

BG = "#08111e"
PANEL = "#132238"
TEXT = "#e9f5ff"
MUTED = "#9ab4cd"
CYAN = "#57e7cc"
AMBER = "#f2c17a"

START_HERE = """CABBAGE CONTROL STUDIO v1.8 / START HERE

1. DRIVE — Use W/A/S/D or hold the nine-direction pad. Release to brake.
   Click ACTIVATE WASD first for real motors. Gears: 1–4.
   ESC / SPACE / EMERGENCY STOP is your software brake.
   ALWAYS keep a physical motor battery cutoff within reach.

2. ROUTES — Create and preview timed, open-loop shapes.
   No encoder, GPS or obstacle detector is integrated with this controller.
   Only attempt a physical route after confirming directions and brakes.

3. SYSTEM — Use WHEEL DOCTOR to isolate physical left/right faults.
   Use POWER PATH LAB if HM-10 works on USB but not motor battery power.
   Use QUICK PREFLIGHT for offline source/packet/stress checks.

4. SAVE TUNING — Stores only harmless steering/calibration preferences.
   Does NOT save a drive-armed state or reconnect automatically.

5. WIRING — First cut motor battery power. Trace Arduino D2/D3 HM-10 UART,
   D4 standby, D5/D6 PWM, D7–D10 direction, motor VM and common GND.
   The exact HM-10 breakout input voltage MUST be checked.
   No LED or firmware PWM report can prove wheel rotation.

6. VERSION — Use matched candidate Arduino firmware for live Wheel Doctor.
   v1.8 is experimental and must not replace a verified production build
   until the physical wheel and emergency stop checks have passed.

"""

def field_manual() -> str:
    file = Path(__file__).resolve().parent / "WHEEL_DOCTOR_FIELD_GUIDE.md"
    try:
        details = file.read_text(encoding="utf-8")
    except OSError:
        details = "The longer Wheel Doctor field guide is not packaged here.\n"
    return START_HERE + "\n\n" + details


class GuideWindow:
    def __init__(self, app):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title("CABBAGE / Operator Guide and Pin Map")
        self.top.geometry("960x750")
        self.top.minsize(680, 470)
        self.top.configure(bg=BG)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.search_text = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Shortcuts, pin map, and safe testing instructions")
        tk.Label(self.top, text="OPERATOR HANDBOOK", bg=BG, fg=CYAN,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=20, pady=(17, 4))
        tk.Label(self.top, text="Read before connecting motors. This window cannot energize the buggy.",
                 bg=BG, fg=AMBER, font=("Segoe UI", 10)).pack(
                     anchor="w", padx=20, pady=(0, 12))
        searchbar = tk.Frame(self.top, bg=PANEL)
        searchbar.pack(fill="x", padx=20, pady=(0, 9))
        tk.Label(searchbar, text="FIND", bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(12, 6), pady=9)
        entry = tk.Entry(searchbar, textvariable=self.search_text,
                         bg="#0c192b", fg=TEXT, insertbackground=CYAN,
                         font=("Segoe UI", 11), relief="flat", width=28)
        entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        entry.bind("<Return>", lambda _e: self.find_next())
        tk.Button(searchbar, text="NEXT MATCH", command=self.find_next,
                  bg="#246c6a", fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=7).pack(
                      side="left", padx=7, pady=6)
        tk.Button(searchbar, text="COPY", command=self.copy,
                  bg="#345572", fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=12, pady=7).pack(
                      side="left", padx=(0, 12))
        content = tk.Frame(self.top, bg=PANEL)
        content.pack(fill="both", expand=True, padx=20, pady=(0, 7))
        scroll = tk.Scrollbar(content)
        scroll.pack(side="right", fill="y")
        self.text = tk.Text(content, bg="#0c192b", fg=TEXT, insertbackground=TEXT,
                            wrap="word", relief="flat", font=("Consolas", 10),
                            padx=15, pady=14, yscrollcommand=scroll.set)
        self.text.pack(fill="both", expand=True)
        scroll.configure(command=self.text.yview)
        self.text.insert("1.0", field_manual())
        self.text.tag_configure("find", background="#2a645e", foreground="#ffffff")
        self.text.configure(state="disabled")
        tk.Label(self.top, textvariable=self.status_text, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 12))

    def find_next(self):
        term = self.search_text.get().strip()
        if not term:
            self.status_text.set("Enter a word or pin (e.g. D6, BLE, RIGHT).")
            return False
        self.text.tag_remove("find", "1.0", "end")
        start = self.text.index("insert")
        pos = self.text.search(term, start, stopindex="end", nocase=True)
        if not pos:
            pos = self.text.search(term, "1.0", stopindex="end", nocase=True)
        if not pos:
            self.status_text.set("No matches for " + term[:40])
            return False
        end = f"{pos}+{len(term)}c"
        self.text.tag_add("find", pos, end)
        self.text.mark_set("insert", end)
        self.text.see(pos)
        self.status_text.set(f"Found {term[:40]} at {pos}")
        return True

    def copy(self):
        self.top.clipboard_clear()
        self.top.clipboard_append(self.text.get("1.0", "end"))

    def close(self):
        self.app.guide_window = None
        self.top.destroy()
