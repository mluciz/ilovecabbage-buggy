/*
  ISOLATED SENSOR BENCH - THREE VL53L0X + MPU-6500
  DOES NOT CONTROL MOTORS. NOT a replacement for the normal buggy firmware.

  IMPORTANT: Disconnect motor battery entirely before upload/bench tests.
  XSHUT logic must not be exposed to 5V. Here we pull each line LOW with an
  Uno pin, then RELEASE it to high impedance (INPUT), NEVER drive HIGH.
  This assumes each XSHUT has a verified pull-up to a safe 2.8V/3.3V rail.
  I2C SDA/SCL require electrical compatibility / proper bidirectional level
  shifting with 5V Uno. Verify your actual breakouts, regulator, current budget,
  common GND, and XSHUT pullups BEFORE powering.

  Libraries: Pololu VL53L0X (install via Arduino Library Manager).
  MPU-6500 gyroscope and accelerometer use I2C register reads (0x68 default).
  Dedicated safe-on-bench example only; NOT integrated with drive control.
*/
#include <Arduino.h>
#include <Wire.h>
#include <VL53L0X.h>

const byte XSHUT_PINS[3] = {A0, A1, A2};
const byte TOF_ADDRS[3] = {0x30, 0x31, 0x32};
const byte MPU_ADDR = 0x68;  // Verify AD0 configuration; might be 0x69.
VL53L0X tof[3];
bool imuReady = false;
unsigned long lastSampleMillis = 0;

void haltWithError(const __FlashStringHelper* message) {
  Serial.print(F("SENSOR_BENCH_ERROR: "));
  Serial.println(message);
  while (true) delay(1000);
}
bool writeRegister(byte address, byte reg, byte data) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(data);
  return Wire.endTransmission() == 0;
}
bool readMpuRaw(int16_t values[6]) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write((byte)0x3B);  // accel X high
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 14) != 14) return false;
  byte raw[14];
  for (int i=0;i<14;++i) raw[i] = (byte)Wire.read();
  // Skip temperature, bytes 6..7.
  for (int axis=0;axis<3;++axis)
    values[axis] = (int16_t)(((uint16_t)raw[axis*2] << 8) | raw[axis*2+1]);
  for (int axis=0;axis<3;++axis)
    values[3+axis] = (int16_t)(((uint16_t)raw[8+axis*2] << 8) | raw[9+axis*2]);
  return true;
}
void printRange(byte index) {
  const unsigned int distance = tof[index].readRangeContinuousMillimeters();
  const bool good = !tof[index].timeoutOccurred() && distance >= 20 && distance <= 2000;
  if (index) Serial.print(',');
  Serial.print(F("{\"id\":\""));
  Serial.print(index == 0 ? F("front") : (index == 1 ? F("left") : F("right")));
  Serial.print(F("\",\"valid\":"));
  Serial.print(good ? F("true") : F("false"));
  if (good) {
    Serial.print(F(",\"distance_mm\":"));
    Serial.print(distance);
  }
  Serial.print('}');
}
void setup() {
  Serial.begin(115200);
  // Set STBY physically inactive / motor battery disconnected externally.
  for (byte i=0;i<3;++i) {
    pinMode(XSHUT_PINS[i], OUTPUT);
    digitalWrite(XSHUT_PINS[i], LOW);
  }
  delay(40);
  Wire.begin();
  // Only use 100 kHz until real wiring and logic levels are verified.
  Wire.setClock(100000);
  for (byte i=0;i<3;++i) {
    // High-Z release; XSHUT is raised ONLY by the verified safe-voltage pull-up.
    pinMode(XSHUT_PINS[i], INPUT);
    delay(30);
    if (!tof[i].init()) haltWithError(F("VL53L0X init failed; check power/XSHUT/I2C"));
    tof[i].setAddress(TOF_ADDRS[i]);
    tof[i].setTimeout(65);
    tof[i].startContinuous(70);
  }
  // MPU-6500: wake and configure +/-2g, +/-250 deg/s.
  imuReady = writeRegister(MPU_ADDR, 0x6B, 0x00) &&
             writeRegister(MPU_ADDR, 0x1B, 0x00) &&
             writeRegister(MPU_ADDR, 0x1C, 0x00);
  if (!imuReady) Serial.println(F("SENSOR_BENCH_WARN: MPU-6500 not detected"));
  lastSampleMillis = millis();
}
void loop() {
  unsigned long now = millis();
  const float dt = (now - lastSampleMillis) / 1000.0f;
  lastSampleMillis = now;

  int16_t mpu[6] = {0,0,0,0,0,0};
  const bool imuValid = imuReady && dt > 0 && dt <= 0.20f && readMpuRaw(mpu);

  // Every emitted line is one complete schema-2 telemetry packet.
  Serial.print(F("{\"schema\":2,\"source\":\"sensor-bench\",\"sensors\":["));
  for (byte i=0;i<3;++i) printRange(i);
  Serial.print(']');
  if (imuValid) {
    Serial.print(F(",\"imu\":{\"gyro_x_dps\":"));
    Serial.print(mpu[3] / 131.0f, 3);
    Serial.print(F(",\"gyro_y_dps\":"));
    Serial.print(mpu[4] / 131.0f, 3);
    Serial.print(F(",\"gyro_z_dps\":"));
    Serial.print(mpu[5] / 131.0f, 3);
    Serial.print(F(",\"accel_x_g\":"));
    Serial.print(mpu[0] / 16384.0f, 4);
    Serial.print(F(",\"accel_y_g\":"));
    Serial.print(mpu[1] / 16384.0f, 4);
    Serial.print(F(",\"accel_z_g\":"));
    Serial.print(mpu[2] / 16384.0f, 4);
    Serial.print(F(",\"dt_s\":"));
    Serial.print(dt, 4);
    Serial.print('}');
  }
  Serial.println('}');
  delay(65);
}
