"""Safety-first Windows HM-10 Bluetooth LE buggy controller.

This is an auditable alternative to the historical v1.6.4 ZIP GUI, whose
original Python sources were not committed to GitHub. It is not a drop-in
replacement for advanced route-planning/flight-recorder features.

Run from repository root: python -m controller.app
Requires: pip install -r controller/requirements.txt
"""
from __future__ import annotations

import asyncio
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from controller.motion import mix, packet

UART_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
KEEPALIVE_SECONDS = 0.15
GUI_HEARTBEAT_LIMIT = 0.65


class BluetoothWorker(threading.Thread):
    def __init__(self, commands: queue.Queue, reports: queue.Queue,
                 heartbeat: list[float], lock: threading.Lock):
        super().__init__(daemon=True)
        self.commands = commands
        self.reports = reports
        self.heartbeat = heartbeat
        self.lock = lock

    def log(self, value: str) -> None:
        self.reports.put(("log", value))

    def status(self, value: str) -> None:
        self.reports.put(("status", value))

    def run(self) -> None:
        try:
            asyncio.run(self.main())
        except Exception as exc:
            self.status("Worker stopped")
            self.log(f"Unexpected worker error: {exc}")

    async def main(self) -> None:
        client = None
        armed = False
        target = (0, 0)
        last_sent = None
        last_tx = 0.0

        async def send(data: bytes) -> None:
            if client is not None and client.is_connected:
                await client.write_gatt_char(UART_UUID, data, response=False)

        async def latch_stop() -> None:
            nonlocal armed, target, last_sent
            armed = False
            target = (0, 0)
            last_sent = None
            # K works with older v1.6.4 firmware; X latches with v1.6.5.
            await send(b"K")
            await send(b"X")

        async def disconnect() -> None:
            nonlocal client
            if client is not None:
                try:
                    if client.is_connected:
                        await latch_stop()
                        await client.disconnect()
                finally:
                    client = None
                    self.status("Disconnected")

        try:
            while True:
                try:
                    action, value = self.commands.get_nowait()
                except queue.Empty:
                    action = None
                    value = None

                try:
                    if action == "shutdown":
                        break
                    if action == "scan":
                        from bleak import BleakScanner
                        self.status("Scanning (motors remain stopped)…")
                        found = await BleakScanner.discover(timeout=5.0)
                        options = [(d.name or "Unnamed") + " — " + d.address
                                   for d in found]
                        self.reports.put(("devices", options))
                        self.status("Select the HM-10 / HMSoft device")
                    elif action == "connect":
                        from bleak import BleakClient
                        await disconnect()
                        address = str(value).strip()
                        if not address:
                            raise ValueError("Select or enter a BLE device address")
                        self.status("Connecting…")
                        client = BleakClient(address, timeout=10.0)
                        await client.connect()
                        if client.services.get_characteristic(UART_UUID) is None:
                            raise RuntimeError("HM-10 FFE1 UART characteristic unavailable")
                        await latch_stop()  # Never arm merely by connecting.
                        self.status("Connected — BRAKED; click ARM to drive")
                        self.log("BLE connected. Startup K + X latch sent.")
                    elif action == "arm":
                        if client is not None and client.is_connected:
                            # Existing firmware accepts M,0,0; new firmware
                            # also requires U after latching emergency stop.
                            await send(b"U")
                            await send(packet(0, 0))
                            armed = True
                            target = (0, 0)
                            last_sent = None
                            self.status("Armed — hold WASD or use direction pads")
                    elif action == "drive":
                        # Never queue any new motor motion while disarmed.
                        target = tuple(value) if armed else (0, 0)
                    elif action == "stop":
                        target = (0, 0)
                        await send(b"K")
                        await send(packet(0, 0))  # Clear ordinary K lockout.
                        last_sent = None
                        self.status("STOP / BRAKED")
                    elif action == "estop":
                        await latch_stop()
                        self.status("E-STOP LATCHED — inspect, then ARM manually")
                    elif action == "disconnect":
                        await disconnect()

                    if client is not None and not client.is_connected:
                        client = None
                        target = (0, 0)
                        armed = False
                        self.status("BLE link lost — firmware watchdog must brake")
                    if client is not None and armed:
                        with self.lock:
                            last_gui_heartbeat = self.heartbeat[0]
                        if time.monotonic() - last_gui_heartbeat > GUI_HEARTBEAT_LIMIT:
                            await latch_stop()
                            self.status("E-STOP: UI heartbeat lost")
                        else:
                            now = time.monotonic()
                            if target != last_sent or (
                                target != (0, 0)
                                and now - last_tx >= KEEPALIVE_SECONDS
                            ):
                                await send(packet(*target))
                                last_sent = target
                                last_tx = now
                except Exception as exc:
                    self.log(f"{action or 'BLE'}: {exc}")
                    try:
                        await latch_stop()
                    except Exception as stop_exc:
                        self.log(f"Stop attempt failed: {stop_exc}")
                    self.status("Fault — DISARMED / check physical motor switch")
                    if action in ("connect", "scan"):
                        try:
                            await disconnect()
                        except Exception:
                            pass
                await asyncio.sleep(0.025)
        finally:
            try:
                await disconnect()
            except Exception as exc:
                self.log(f"BLE shutdown: {exc}")


class BuggyApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Buggy — Safe Wheel Control")
        self.root.geometry("720x660")
        self.root.minsize(570, 575)
        self.keys: set[str] = set()
        self.release_timers: dict[str, str] = {}
        self.speed = tk.IntVar(value=160)
        self.status_text = tk.StringVar(value="Disconnected — motor power OFF for setup")
        self.device_text = tk.StringVar()
        self.commands: queue.Queue = queue.Queue()
        self.reports: queue.Queue = queue.Queue()
        self.heartbeat = [time.monotonic()]
        self.lock = threading.Lock()
        self.worker = BluetoothWorker(self.commands, self.reports,
                                       self.heartbeat, self.lock)
        self.worker.start()
        self._make_widgets()
        root.bind_all("<KeyPress>", self.on_key_press, add="+")
        root.bind_all("<KeyRelease>", self.on_key_release, add="+")
        root.bind("<FocusOut>", self.on_focus_out, add="+")
        root.protocol("WM_DELETE_WINDOW", self.shutdown)
        root.after(100, self.tick)

    def _make_widgets(self) -> None:
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Buggy Wheel Control",
                  font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Open-loop PWM control · Wheels must be raised during calibration",
                  foreground="#805400").pack(anchor="w", pady=(4, 14))
        connection = ttk.Frame(outer)
        connection.pack(fill="x")
        ttk.Label(connection, text="HM-10 BLE device / address").pack(anchor="w")
        self.device_picker = ttk.Combobox(connection, textvariable=self.device_text)
        self.device_picker.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(connection, text="Scan", command=lambda: self.send("scan")).pack(side="left")
        ttk.Button(connection, text="Connect",
                   command=lambda: self.send("connect", self.selected_device())).pack(side="left", padx=5)
        ttk.Button(connection, text="Disconnect",
                   command=lambda: self.send("disconnect")).pack(side="left")
        ttk.Label(outer, textvariable=self.status_text, wraplength=650,
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=18)
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=10)
        ttk.Button(controls, text="ARM (manual reset)",
                   command=self.arm).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ttk.Button(controls, text="STOP / BRAKE",
                   command=self.stop).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(controls, text="EMERGENCY STOP",
                   command=self.estop).pack(side="left", expand=True, fill="x", padx=(5, 0))
        ttk.Label(outer, text="Speed (start low with wheels raised)").pack(anchor="w", pady=(15, 3))
        ttk.Scale(outer, from_=80, to=220, orient="horizontal",
                  variable=self.speed, command=lambda _: self.publish_motion()).pack(fill="x")
        ttk.Label(outer, text="W = forward · S = reverse · A/D = turn · W+A = gentle left · Esc = E-STOP").pack(anchor="w", pady=8)
        pad = ttk.Frame(outer)
        pad.pack(pady=15)
        button_specs = [("W", 0, 1, "w"), ("A", 1, 0, "a"), ("S", 1, 1, "s"), ("D", 1, 2, "d")]
        for text, row, col, key in button_specs:
            btn = ttk.Button(pad, text=text, width=12)
            btn.grid(row=row, column=col, padx=6, pady=6, ipadx=3, ipady=8)
            btn.bind("<ButtonPress-1>", lambda e, k=key: self.press(k))
            btn.bind("<ButtonRelease-1>", lambda e, k=key: self.release(k))
        ttk.Label(outer, text="Diagnostics (commands are not wheel-speed measurements)").pack(anchor="w")
        self.logbox = tk.Text(outer, height=8, state="disabled", wrap="word")
        self.logbox.pack(fill="both", expand=True, pady=5)
        ttk.Label(outer, text="WARNING: a broken motor-driver channel cannot be fixed in software. "
                  "Keep a physical battery cut-off within reach.", wraplength=650,
                  foreground="#9b341c").pack(anchor="w", pady=(6, 0))

    def send(self, action: str, value=None) -> None:
        self.commands.put((action, value))

    def selected_device(self) -> str:
        value = self.device_text.get().strip()
        return value.rsplit(" — ", 1)[-1]

    def press(self, key: str) -> None:
        if key in self.release_timers:
            self.root.after_cancel(self.release_timers.pop(key))
        if key not in self.keys:
            self.keys.add(key)
            self.publish_motion()

    def release(self, key: str) -> None:
        self.keys.discard(key)
        self.publish_motion()

    def publish_motion(self) -> None:
        self.send("drive", mix(self.keys, int(self.speed.get())))

    def on_key_press(self, event) -> None:
        key = event.keysym.lower()
        if key == "escape":
            self.estop()
            return
        if isinstance(event.widget, (ttk.Entry, ttk.Combobox, tk.Entry, tk.Text)):
            return
        if key in {"w", "a", "s", "d"}:
            self.press(key)

    def on_key_release(self, event) -> None:
        key = event.keysym.lower()
        if key not in {"w", "a", "s", "d"}:
            return
        # Windows key auto-repeat can synthesize KeyRelease+KeyPress pairs.
        if key in self.release_timers:
            self.root.after_cancel(self.release_timers.pop(key))
        self.release_timers[key] = self.root.after(35, lambda k=key: self.delayed_release(k))

    def delayed_release(self, key: str) -> None:
        self.release_timers.pop(key, None)
        self.release(key)

    def clear_keys(self) -> None:
        for timer in self.release_timers.values():
            self.root.after_cancel(timer)
        self.release_timers.clear()
        self.keys.clear()
        self.publish_motion()

    def stop(self) -> None:
        self.clear_keys()
        self.send("stop")

    def estop(self) -> None:
        self.clear_keys()
        self.send("estop")

    def arm(self) -> None:
        self.clear_keys()
        self.send("arm")

    def on_focus_out(self, event) -> None:
        # Child widgets also cause FocusOut; check after focus settles.
        self.root.after(60, self.stop_if_unfocused)

    def stop_if_unfocused(self) -> None:
        if self.root.focus_get() is None:
            self.estop()

    def tick(self) -> None:
        with self.lock:
            self.heartbeat[0] = time.monotonic()
        try:
            while True:
                kind, value = self.reports.get_nowait()
                if kind == "status":
                    self.status_text.set(value)
                elif kind == "devices":
                    self.device_picker["values"] = value
                    if value:
                        self.device_text.set(value[0])
                elif kind == "log":
                    self.logbox.configure(state="normal")
                    self.logbox.insert("end", value + "\n")
                    self.logbox.see("end")
                    self.logbox.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self.tick)

    def shutdown(self) -> None:
        self.clear_keys()
        self.send("shutdown")
        self.root.after(500, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    BuggyApp(root)
    root.mainloop()
