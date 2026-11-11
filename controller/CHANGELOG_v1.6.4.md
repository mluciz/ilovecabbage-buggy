# v1.6.4 — Drive Priority and Link Lab

Built from v1.6.3 (not v1.7). Compatible with original Uno D4–D10 and HM-10 D2/D3 wiring.

## Reliability fixes

1. **Stop transmitting optional SoftwareSerial UART telemetry while either wheel is powered.** At 9600 baud, SoftwareSerial transmitting bytes can disable reception of subsequent motor packets; this is a plausible explanation for intermittent WASD freezes. Handshake and telemetry output are deferred until the buggy is braked. The application displays an explicit *telemetry paused during driving* state instead of a false stale-link alarm.
2. **Timeout stuck Windows GATT writes after 850 ms.** The transport fails closed and disconnects instead of allowing the control task to hang forever; this doesn't guarantee the hardware brakes, which remains dependent on the TB6612FNG and firmware watchdog.
3. **Watchdog lockout:** The Uno brakes after 1,200 ms without fresh motor commands and ignores subsequent nonzero packets until a deliberate `K` or `M,0,0`. Prevents automatic restart after a dropout. The GUI issues a brake and requires key release if it learns of a watchdog stop.
4. **Lower BLE idle traffic:** drive every ~120 ms, idle/brake every ~300 ms, immediate release-to-brake preserved.
5. **Escape emergency brake from any focus**, including text fields; Space remains brake when not typing.

## New functionality

- **Accepted command counter** in extended v1.6.4 Arduino telemetry: `T,<left>,<right>,<state>,<seq>,<accepted_count>`. Old five-field telemetry still parses. These are counters of successfully parsed motor commands, never actual wheel sensor data. The counter is shown and exported to the flight recorder only after Arduino becomes idle.
- **Precision drive checkbox** for manual-only lower gears 110, 150, 200, 240 PWM. Boost profile remains 220/255/255/255 by default, as requested earlier. Changing mode with keys held brakes and requires deliberate re-press.
- **OFFLINE LINK STRESS** checks deterministic virtual packet loss/jitter and a 2-second simulated outage, without connecting to Bluetooth or moving a motor.
- Expanded tests for receiver counter bounds, no-transmit-while-driving firmware, stuck BLE writes, watchdog lockout, precision mode, global Escape and link simulation.

## Important limitations

- The telemetry counter and a successful BLE write **do not prove the right wheel moves**, or that active braking physically works. Sensorless software cannot distinguish a shorted/failed B-channel from wiring/power issues.
- Motor telemetry during movement is intentionally unavailable in v1.6.4; inspect the counter after releasing the drive key. Firmware status during an outage may only arrive after braking.
- Automatic tracks, motor pin mappings, motor test sketch and existing controls are retained. Physical battery switch and STBY pulldown remain important.
- Regression tests simulate Arduino pins and Windows GUI behavior; no actual HM-10, motors or Uno were attached, and the firmware has not been compiled using the official Arduino board toolchain.
