"""Safe offline preflight report window. Real BLE motor link must be disconnected."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from preflight import run_preflight


class PreflightWindow:
    def __init__(self, app):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title("CABBAGE / Offline preflight")
        self.top.geometry("900x680")
        self.top.minsize(680, 440)
        self.top.configure(bg="#08111e")
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        tk.Label(self.top, text="PRE-FLIGHT / OFFLINE",
                 bg="#08111e", fg="#57e7cc",
                 font=("Segoe UI", 23, "bold")).pack(anchor="w", padx=21, pady=(17, 3))
        tk.Label(self.top,
                 text="One click: controller math + packet formatting + source pin audit + synthetic link outages",
                 bg="#08111e", fg="#9ab4cd", font=("Segoe UI", 10)).pack(
                     anchor="w", padx=22, pady=(0, 11))
        self.status = tk.StringVar(value="Ready")
        topbar = tk.Frame(self.top, bg="#132238")
        topbar.pack(fill="x", padx=21, pady=(0, 9))
        for title, fn, color in (
            ("RUN AGAIN", self.refresh, "#246f6d"),
            ("COPY REPORT", self.copy, "#355674"),
            ("SAVE REPORT", self.save, "#355674"),
        ):
            tk.Button(topbar, text=title, command=fn, bg=color, fg="white",
                      activebackground="#57e7cc", relief="flat", padx=12, pady=9,
                      font=("Segoe UI", 9, "bold")).pack(side="left", padx=8, pady=9)
        tk.Label(topbar, textvariable=self.status, bg="#132238", fg="#f2c17a",
                 font=("Segoe UI", 10, "bold")).pack(side="right", padx=10)
        frame = tk.Frame(self.top, bg="#0c192b")
        frame.pack(fill="both", expand=True, padx=21, pady=(0, 17))
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        self.report = tk.Text(frame, bg="#0c192b", fg="#e9f5ff",
                              insertbackground="#e9f5ff", font=("Consolas", 9),
                              relief="flat", wrap="word", padx=12, pady=13,
                              yscrollcommand=scrollbar.set)
        self.report.pack(fill="both", expand=True)
        scrollbar.configure(command=self.report.yview)
        self.refresh()

    def refresh(self):
        if self.app.online and not self.app.demo:
            self.app.emergency_stop(quiet=True)
            messagebox.showwarning("Disconnect real BLE first",
                "Preflight is entirely offline. Disconnect the actual motor controller "
                "before running the synthetic checks.", parent=self.top)
            return
        ok, report = run_preflight()
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("1.0", report)
        self.report.configure(state="disabled")
        self.status.set("SOFTWARE CHECKS PASSED" if ok else "CHECKS FAILED / SEE REPORT")

    def copy(self):
        self.top.clipboard_clear()
        self.top.clipboard_append(self.report.get("1.0", "end"))

    def save(self):
        path = filedialog.asksaveasfilename(parent=self.top, defaultextension=".txt",
                    initialfile="cabbage-offline-preflight.txt",
                    filetypes=[("Text", "*.txt")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as output:
                    output.write(self.report.get("1.0", "end"))
            except OSError as exc:
                messagebox.showerror("Unable to save report", str(exc), parent=self.top)

    def close(self):
        self.app.preflight_window = None
        self.top.destroy()
