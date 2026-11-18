# Three VL53L0X + one MPU-6500 — hardware and pin audit

## Existing live controller (read from main, v1.6.4)
- Uno D2 (HM-10 RX via SoftwareSerial), D3 (HM-10 TX), D4 (TB6612 STBY)
- D5/D6 PWMA/PWMB, D7/D8 AIN1/AIN2, D9/D10 BIN1/BIN2
- Arduino motor command telemetry `T,left,right,state,seq,count` contains **PWM commands**, not measured position or velocity.
- The existing firmware **does not emit** 3 VL53L0X ranges, MPU-6500 samples, odometry, wheel encoders, or sensor schema-2 JSON. This branch does **not** change that firmware.

## Sensible future wiring allocation (NOT installed/verified)
- Uno A4=SDA and A5=SCL share the I2C bus; add the MPU-6500 at its verified address (typically 0x68/0x69), and all three VL53L0X units.
- Three **separate XSHUT controls** are necessary for stable address assignment at boot. A0/A1/A2 are currently unused in the inspected v1.6.4 sketch, but electrical compatibility and software timing must be verified before integrating. A0/A1/A2 are used only in the **standalone bench sketch**.
- Example sensor IDs: FRONT = 0x30, LEFT = 0x31, RIGHT = 0x32, assigned **one at a time after reset**. The factory 7-bit VL53L0X address is 0x29. Address assignments are reset after power cycling. Do not hardwire three default-address ToF modules simultaneously without a proper XSHUT init sequence.
- Hardware placement is not confirmed. The Unreal scene currently assumes front 0°, left +55°, right −55°, with approximate sensor offsets. Measure actual angles and offsets before using the map as geometry.

## Electrical safeguards
1. **Physically disconnect the motor battery.** The existing right-wheel safety fault has not been cleared.
2. An Arduino Uno GPIO outputs ~5 V HIGH. Naked VL53L0X XSHUT and MPU-6500 silicon cannot simply be treated as 5-V logic inputs. The isolated sketch drives XSHUT LOW then releases to high impedance; safe pull-ups to the breakout's actual XSHUT logic voltage must be confirmed first.
3. UNO I2C is also 5-V domain: use verified 5-V-tolerant *breakout logic* or proper **bidirectional I2C level shifting** as appropriate. A simple series resistor or capacitors do not make a 5-V I2C bus universally safe.
4. Check the regulator and level-shifting circuitry on **your specific modules**. Some have regulators but not level shifting on every signal. Do not assume the 3.3-V Uno pin can reliably supply three ToFs plus the IMU.
5. Resistors can be useful for pull-ups (to the correct low-voltage rail) or proper level-shifting circuitry. Ceramic decoupling capacitors, often 100 nF near IC supply pins plus local bulk decoupling, can help stability, but first inspect what capacitors are already populated on the modules.
6. Keep common ground, short sensor wires, adequate regulated 3.3/2.8-V power as specified by the actual breakout, and avoid adding parallel pull-ups until the existing onboard pull-ups are known.
7. Bench I2C reliability and address discovery at low bus speed before any motor-power reconnection.

## Testing sequence
- Run Unreal INTERNAL DEMO with no Arduino, then `python tools/demo_sender.py --scenario sensor-dropout` in EXTERNAL mode.
- With motors **physically disconnected** and the electrical checks above done, upload the *separate* `firmware/SensorBench3ToF/SensorBench3ToF.ino` to a bench Arduino. It replaces normal firmware while uploaded; re-upload normal firmware afterwards if returning to driving.
- Bench serial monitor at 115200 should print one JSON telemetry line containing all three ToF channels, and optionally six IMU components. Use `python tools/serial_bridge.py --serial-port COMx` with Serial Monitor closed.
- Do not run Serial Monitor and the Python bridge on the same COM port.
- Integrating 3 ToFs into real-time driving firmware requires a separate safety review for I2C timing, the HM-10 SoftwareSerial window, watchdog behavior, and stack/RAM. No integration is claimed.

## Measurements and limitations
- VL53L0X yields range measurements, not object type, surface dimensions, or direct azimuth; mounting directions supply approximate bearings.
- MPU-6500 provides angular rates and accelerations; yaw integration drifts without heading reference. Pitch/roll complementary estimates are sensitive to acceleration, sensor axis mounting and calibration.
- No actual ground-frame X/Y pose source exists in the present firmware. The Unreal live view shows hit positions relative to an unverified frame unless an **external** pose estimate is supplied. Do not call it reliable SLAM.

References:
- ST application note AN4846, Using Multiple VL53L0X in a Single Design:
  https://www.st.com/resource/en/application_note/an4846-using-multiple-vl53l0x-in-a-single-design-stmicroelectronics.pdf
- Adafruit multi-sensor explanation:
  https://learn.adafruit.com/adafruit-vl53l0x-time-of-flight-micro-lidar-distance-sensor-breakout/arduino-code
