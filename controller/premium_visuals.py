"""Professional canvas visuals for the Buggy Field Console.

Only commanded PWM is visualized. No wheel sensor or speed inference.
The functions are deliberately independent of Bluetooth and can be exercised
with a regular Tk Canvas in the offline demo.
"""
from __future__ import annotations

BG = "#0c1828"
GRID = "#182a3e"
STROKE = "#34506b"
TEAL = "#54e2c5"
VIOLET = "#799cff"
AMBER = "#f5bd79"
TEXT = "#ecf5ff"
MUTED = "#8fa9c1"


def clamp_pwm(value: int | float) -> int:
    return max(-255, min(255, round(value)))


def command_label(value: int | float) -> str:
    value = clamp_pwm(value)
    if value > 0:
        return f"FWD  {value:03d}"
    if value < 0:
        return f"REV  {abs(value):03d}"
    return "BRAKE / 000"


def _rounded(canvas, x0, y0, x1, y1, radius=12, *, fill, outline="", width=1):
    r = min(radius, (x1-x0)/2, (y1-y0)/2)
    pts = [x0+r,y0,x1-r,y0,x1,y0,x1,y0+r,x1,y1-r,x1,y1,
           x1-r,y1,x0+r,y1,x0,y1,x0,y1-r,x0,y0+r,x0,y0]
    return canvas.create_polygon(pts, smooth=True, splinesteps=14,
                                 fill=fill, outline=outline, width=width)


def render_drive(canvas, left: int, right: int, mode: str, safe: bool):
    """Two-channel motor sketch, not wheel telemetry."""
    canvas.delete("all")
    width = max(320, canvas.winfo_width())
    height = max(242, canvas.winfo_height())
    sx = width / 2
    sy = height * 0.51
    for x in range(0, width + 28, 32):
        canvas.create_line(x, 0, x, height, fill=GRID)
    for y in range(0, height + 28, 32):
        canvas.create_line(0, y, width, y, fill=GRID)

    canvas.create_text(21, 20, anchor="w", text="LIVE OUTPUT  /  PWM COMMAND",
                       fill=TEAL, font=("Segoe UI", 10, "bold"))
    canvas.create_text(width-18, 20, anchor="e",
                       text=mode.upper(), fill=AMBER if safe else MUTED,
                       font=("Consolas", 9, "bold"))
    # A clean diagram of the chassis and two differential-drive channels.
    body_width = min(190, width * .40)
    bx0, bx1 = sx-body_width/2, sx+body_width/2
    by0, by1 = sy-72, sy+77
    _rounded(canvas, bx0, by0, bx1, by1, 22, fill="#1c3047", outline=STROKE, width=2)
    _rounded(canvas, bx0+15, by0+15, bx1-15, by1-15, 15,
             fill="#112235", outline="#2d4b65", width=1)
    canvas.create_line(sx, by0+30, sx, by1-30, fill="#3b6178", width=1, dash=(3,4))
    canvas.create_polygon(sx,by0+21,sx-13,by0+44,sx+13,by0+44,
                          fill=TEAL, outline="")
    canvas.create_text(sx, sy-13, text="BUGGY", fill=TEXT,
                       font=("Segoe UI", 15, "bold"))
    canvas.create_text(sx, sy+13, text="TB6612FNG", fill=MUTED,
                       font=("Consolas", 9))
    canvas.create_text(sx, sy+34, text="A / B MOTOR DRIVER", fill=MUTED,
                       font=("Segoe UI", 8))
    for sign, val, label in ((-1,left,"LEFT / A"), (1,right,"RIGHT / B")):
        x = sx + sign*(body_width/2+13)
        wheel_x0 = x-14
        _rounded(canvas,wheel_x0,sy-49,wheel_x0+28,sy+54,10,
                 fill="#08111e",outline=TEAL if val else "#456078",width=2)
        for dy in range(-35,50,14):
            canvas.create_line(wheel_x0+6,sy+dy,wheel_x0+22,sy+dy,
                               fill="#30506d",width=2)
        # Each wheel is connected via a visual signal line; never implies motion.
        canvas.create_line(sx+sign*(body_width/2),sy,
                           wheel_x0+14,sy,fill=TEAL if val else STROKE,width=3)
        label_x = 22 if sign<0 else width-22
        anchor = "w" if sign<0 else "e"
        canvas.create_text(label_x,sy-32,anchor=anchor,text=label,
                           fill=MUTED,font=("Segoe UI",9,"bold"))
        canvas.create_text(label_x,sy-4,anchor=anchor,text=command_label(val),
                           fill=TEAL if val>0 else AMBER if val<0 else TEXT,
                           font=("Consolas",12,"bold"))
        bar_w = max(28,min(96,(width-body_width)/4))
        start = 22 if sign<0 else width-22-bar_w
        _rounded(canvas,start,sy+17,start+bar_w,sy+24,3,
                 fill="#29415a")
        if val:
            _rounded(canvas,start,sy+17,start+max(2,bar_w*abs(clamp_pwm(val))/255),
                     sy+24,3,fill=TEAL if val>0 else AMBER)
    canvas.create_text(width/2,height-18,
                       text="COMMAND SIGNAL ONLY  /  WHEEL RPM & MOTION NOT MEASURED",
                       fill=AMBER,font=("Segoe UI",9,"bold"))


def render_link_health(canvas, connected: bool, arduino_reply: bool, last_write_age: float | None):
    """Simple three-layer link visualization without falsely claiming physical motor success."""
    canvas.delete("all")
    w = max(300, canvas.winfo_width())
    for i, (title, ok, sub) in enumerate((
        ("WINDOWS", True, "INPUT"),
        ("BLE LINK", connected, "GATT"),
        ("ARDUINO", arduino_reply, "UART RX"))):
        x = 16 + i*(w-32)/3
        circle_x = x + 22
        canvas.create_oval(circle_x-7,10,circle_x+7,24,
                           fill=TEAL if ok else "#4c6177",outline="")
        canvas.create_text(x+35,17,text=title,anchor="w",fill=TEXT if ok else MUTED,
                           font=("Segoe UI",9,"bold"))
        canvas.create_text(x+13,42,text=sub,anchor="w",fill=MUTED,font=("Consolas",8))
        if i<2:
            canvas.create_line(x+106,17,x+(w-32)/3-7,17,fill=STROKE,width=2)
    canvas.create_text(w-13,62,anchor="e",
                       text=("Last BLE write %.2fs ago" % last_write_age
                             if last_write_age is not None else "No BLE write recorded"),
                       fill=AMBER if (last_write_age is not None and last_write_age>.6) else MUTED,
                       font=("Consolas",8))
