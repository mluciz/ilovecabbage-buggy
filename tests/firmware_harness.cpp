#include "arduino_stubs/Arduino.h"
#include "arduino_stubs/SoftwareSerial.h"

unsigned long simulatedMillis = 0;
FakeHardwareSerial Serial;
int digitalPins[20] = {};
int pwmPins[20] = {};
unsigned long millis() { return simulatedMillis; }
void pinMode(byte,int) {}
void digitalWrite(byte pin,int value) { digitalPins[pin]=value; }
void analogWrite(byte pin,int value) { pwmPins[pin]=value; }

#include "../controller/arduino/BuggyController/BuggyController.ino"

void ble(const char* bytes) { BT.rx += bytes; loop(); }
void usb(const char* bytes) { Serial.rx += bytes; loop(); }
void later(unsigned long n) { simulatedMillis += n; loop(); }

void braked() {
  assert(currentLeft==0 && currentRight==0);
  assert(digitalPins[AIN1]==HIGH && digitalPins[AIN2]==HIGH);
  assert(digitalPins[BIN1]==HIGH && digitalPins[BIN2]==HIGH);
  assert(pwmPins[PWMA]==255 && pwmPins[PWMB]==255);
}
int main() {
  setup();
  braked();
  assert(digitalPins[STBY]==HIGH);
  ble("M,150,150\n");
  assert(currentLeft==150 && currentRight==150);
  assert(digitalPins[AIN1]==HIGH && digitalPins[AIN2]==LOW);
  assert(digitalPins[BIN1]==HIGH && digitalPins[BIN2]==LOW);

  // Forward to pivot must stop both motors before reversing a channel.
  ble("M,150,-150\n");
  braked();
  assert(reversalPending);
  later(69);
  braked();
  later(1);
  assert(currentLeft==150 && currentRight==-150);
  assert(digitalPins[BIN1]==LOW && digitalPins[BIN2]==HIGH);

  // An emergency stop during reversal must cancel pending motion forever.
  ble("M,-150,150\n");
  assert(reversalPending);
  ble("K");
  braked();
  assert(!reversalPending && watchdogLockout);
  later(400);
  braked();
  ble("M,100,100\n"); // No fresh release yet.
  braked();
  ble("M,0,0\n");
  ble("M,100,100\n");
  assert(currentLeft==100 && currentRight==100);

  // USB and BLE must have independent partial-frame buffers.
  ble("K");
  ble("M,0,0\n");
  ble("M,100,");           // Incomplete BLE packet.
  usb("M,0,0\n");         // USB must not overwrite BLE bytes.
  ble("70\n");
  assert(currentLeft==100 && currentRight==70);

  // A corrupted/oversized drive frame must not command wheels.
  ble("K"); ble("M,0,0\n");
  ble("M,9999,1\n");
  braked();
  ble("M,100,100\n");
  assert(currentLeft==100 && currentRight==100);

  // Watchdog should latch, then only release on zero frame.
  later(WATCHDOG_MS+1);
  braked();
  assert(driveState=='W' && watchdogLockout);
  ble("M,160,160\n");
  braked();
  ble("M,0,0\n");
  ble("M,160,160\n");
  assert(currentLeft==160 && currentRight==160);

  // Emergency X is stronger: zero frame alone cannot clear the latch.
  ble("X"); braked();
  assert(eStopLatched);
  ble("M,0,0\n");
  ble("M,150,150\n");
  braked();
  ble("U");
  assert(!eStopLatched);
  ble("M,0,0\n");
  ble("M,150,150\n");
  assert(currentLeft==150 && currentRight==150);

  // A stop frame during reversal must never be replayed later.
  ble("M,-150,-150\n");
  assert(reversalPending);
  ble("M,0,0\n");
  later(REVERSAL_BRAKE_MS+1);
  braked();

  // Malformed fragments and timeout must not start the motors.
  ble("M,100,");
  later(PACKET_TIMEOUT_MS+1);
  ble("100\n");
  braked();
  std::puts("Firmware motion/parsing/interlock simulator: PASS");
}
