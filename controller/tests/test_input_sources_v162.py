"""Mouse/keyboard should independently control a common held direction."""
import time
import tkinter as tk
from app import BuggyApp


def test_mouse_release_does_not_cancel_keyboard_held_w():
    root = tk.Tk()
    try:
        app = BuggyApp(root)
        root.update()
        app.demo_var.set(True)
        app.toggle_connection()
        app._press('W', source='keyboard')
        app._press('W', source='mouse')
        app._release('W', source='mouse')
        assert app.pressed == {'W'}
        assert not app.brake_latched
        app._release('W', source='keyboard')
        assert app.pressed == set()
        assert app.brake_latched
        app._shutdown()
    finally:
        root.destroy()


def test_brake_cannot_be_cancelled_by_windows_repeat_keyup():
    root = tk.Tk()
    try:
        app = BuggyApp(root)
        root.update()
        app.demo_var.set(True)
        app.toggle_connection()
        app._press('W', source='keyboard')
        app.emergency_stop()
        fake = type('Event', (), {'keysym': 'w', 'char': 'w'})()
        app._key_up(fake)     # possible synthetic release
        app._key_down(type('Event', (), {'keysym': 'w', 'char': 'w',
                                        'widget': app.drive_panel})())
        assert app.brake_latched
        assert not app.pressed
        # A *real* keyup, followed by debounce, must re-arm W.
        app._key_up(fake)
        time.sleep(0.09)
        root.update()
        app._press('W', source='keyboard')
        assert not app.brake_latched
        app._shutdown()
    finally:
        root.destroy()


def test_activate_keyboard_recovers_from_old_latched_block():
    root = tk.Tk()
    try:
        app = BuggyApp(root)
        root.update()
        app.demo_var.set(True)
        app.toggle_connection()
        app._press('S', source='keyboard')
        app.emergency_stop()
        assert 'S' in app._blocked_drive_keys
        app.activate_keyboard()
        assert not app._blocked_drive_keys  # non-Windows test environment
        app._press('S', source='keyboard')
        assert app.pressed == {'S'}
        app._shutdown()
    finally:
        root.destroy()
