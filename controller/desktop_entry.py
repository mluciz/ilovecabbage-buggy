"""Windows GUI entry point for the installed Cabbage Control Studio.

Never opens a console, never auto-connects a motor, and never auto-arms.
If a startup crash occurs, show a friendly dialog and save a diagnostic log
instead of silently disappearing (PyInstaller --windowed hides stderr).
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback
from datetime import datetime


def diagnostics_dir() -> Path:
    if os.name == "nt":
        parent = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        return parent / "CabbageControlStudio" / "Logs"
    return Path.home() / ".local" / "state" / "cabbage-control-studio" / "logs"


def save_crash_report(exc: BaseException) -> Path | None:
    try:
        folder = diagnostics_dir()
        folder.mkdir(parents=True, exist_ok=True)
        # Avoid writing secrets, BLE addresses or persisted app settings.
        # Last startup only; cap disk usage to a single overwritten traceback.
        path = folder / "startup-error.txt"
        lines = [
            "CABBAGE Control Studio v1.8 / startup diagnostics",
            f"Timestamp (local): {datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"Python frozen: {bool(getattr(sys, 'frozen', False))}",
            f"OS: {os.name}",
            "",
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
    except OSError:
        return None


def show_dialog(title: str, message: str) -> None:
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000010)
        else:
            from tkinter import Tk, messagebox
            root = Tk()
            root.withdraw()
            messagebox.showerror(title, message, parent=root)
            root.destroy()
    except Exception:
        pass


def one_instance_on_windows():
    """Prevent two desktop instances from sending commands to one BLE device."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    name = r"Local\CabbageControlStudio_1_8"
    mutex = kernel32.CreateMutexW(None, True, name)
    if not mutex:
        raise OSError(ctypes.get_last_error(), "Unable to open application mutex")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(mutex)
        show_dialog("CABBAGE Control Studio",
                    "CABBAGE Control Studio is already open.\n\n"
                    "Use its existing window so the buggy has only one controller.")
        return False
    return (kernel32, mutex)


def launch() -> int:
    handle = None
    try:
        handle = one_instance_on_windows()
        if handle is False:
            return 0
        # Import lazily so all dependency failures enter the GUI error path.
        from app import main
        main()
        return 0
    except Exception as exc:
        error_path = save_crash_report(exc)
        hint = (f"\n\nDetails saved to:\n{error_path}" if error_path
                else "\n\nUnable to save diagnostic details.")
        show_dialog("CABBAGE Control Studio — startup problem",
                    "The app could not start. No motor connection was opened.\n"
                    "Try reinstalling the candidate app or view the startup report."
                    + hint)
        return 1
    finally:
        if isinstance(handle, tuple):
            kernel32, mutex = handle
            # Closing the handle frees the mutex automatically on process exit.
            kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    raise SystemExit(launch())
