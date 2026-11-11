#include <SoftwareSerial.h>
#include <stdlib.h>
#include <string.h>

/*
  BUGGY CONTROL CENTER v1.6.4 (based on v1.6.3)
  Arduino Uno + TB6612FNG + HM-10 at 9600 baud

  Pins are unchanged from v1.1:
  D4 STBY, D5 PWMA, D6 PWMB, D7 AIN1, D8 AIN2, D9 BIN1, D10 BIN2
  D2 RX from HM-10 TX, D3 TX to HM-10 RX via 3.3 V logic-level divider

  Incoming BLE/USB commands (only framed M packets drive via BLE):
    M,<left>,<right>\n   Signed PWM (-255..255), 0,0 = ACTIVE BRAKE
    K\n                 Both wheels ACTIVE SHORT BRAKE (TB6612FNG IN1=IN2=HIGH)
    Q\n                 Safe firmware handshake: replies H,13\n
    Legacy F B L R S 1 2 3 4 also supported for basic debugging

  Outgoing HM-10 UART telemetry at most every 1000 ms when RX idle:
    T,<left>,<right>,<state>,<seq>,<accepted_count>\n
    state D=drive C=coast B=active brake W=watchdog brake
  These are the driver PWM COMMANDS, NOT wheel-speed measurements.
  Requires a BLE characteristic supporting notifications (typically FFE1).

  WARNING: The label "cabbagelover" in the app does NOT rename your HM-10.
*/

const byte STBY = 4;
const byte PWMA = 5;
const byte PWMB = 6;
const byte AIN1 = 7;
const byte AIN2 = 8;
const byte BIN1 = 9;
const byte BIN2 = 10;

const int LEFT_MOTOR_POLARITY = 1;  // Change to -1 if this motor turns backward.
const int RIGHT_MOTOR_POLARITY = 1;

SoftwareSerial BT(2, 3);
// BLE UART packets can be delayed by Windows BLE scheduling and SoftwareSerial.
// Allow a short interruption without stalling, but always stop after a lost link.
const unsigned long WATCHDOG_MS = 1200;
// Fewer outgoing SoftwareSerial bytes means fewer missed inbound drive frames.
const unsigned long TELEMETRY_MS = 1000;
// SoftwareSerial is half-duplex: sending telemetry while the wheels run can
// silently drop incoming motor commands. Prioritize drive safety and report
// received packet count once the driver is braked.
const bool TELEMETRY_WHILE_MOVING = false;
// SoftwareSerial cannot receive reliably while sending. Let incoming bytes
// finish first and leave an idle gap before transmitting optional telemetry.
const unsigned long RX_QUIET_MS = 45;
const unsigned long PACKET_TIMEOUT_MS = 180;
unsigned long lastRxByteAt = 0;
unsigned long lastMotionCommand = 0;
unsigned long lastTelemetry = 0;
unsigned int telemetrySeq = 0;
unsigned long acceptedDrivePackets = 0;
int legacySpeed = 150;
int legacyLeftDir = 0;
int legacyRightDir = 0;
int currentLeft = 0;
int currentRight = 0;
char driveState = 'C';
// After a watchdog stop, stale/replayed drive packets must not restart motors.
bool watchdogLockout = false;

char packet[24];
byte packetPos = 0;
bool receivingPacket = false;
bool handshakePending = false;

void motorDrive(byte pwm, byte in1, byte in2, int signedPower) {
  signedPower = constrain(signedPower, -255, 255);
  analogWrite(pwm, 0);
  if (signedPower == 0) {
    // Hold an idle wheel in short brake, even when the other wheel is driven.
    // Otherwise a zero-power wheel COASTS and the buggy keeps drifting/turning.
    digitalWrite(in1, HIGH);
    digitalWrite(in2, HIGH);
    analogWrite(pwm, 255);
    return;
  }
  digitalWrite(in1, signedPower > 0 ? HIGH : LOW);
  digitalWrite(in2, signedPower > 0 ? LOW : HIGH);
  analogWrite(pwm, abs(signedPower));
}

void activeBrake(char state = 'B');

void commandWheels(int left, int right) {
  // Zero drive means BRAKE rather than coast: a held key may be lost by BLE.
  if (left == 0 && right == 0) {
    activeBrake();
    return;
  }
  currentLeft = constrain(left, -255, 255);
  currentRight = constrain(right, -255, 255);
  motorDrive(PWMA, AIN1, AIN2, currentLeft * LEFT_MOTOR_POLARITY);
  motorDrive(PWMB, BIN1, BIN2, currentRight * RIGHT_MOTOR_POLARITY);
  driveState = (currentLeft || currentRight) ? 'D' : 'C';
  lastMotionCommand = millis();
}

void activeBrake(char state) {
  // Toshiba TB6612FNG datasheet: IN1=IN2=HIGH, STBY=HIGH => short brake.
  // This stops the wheels more decisively than simply removing drive.
  currentLeft = 0;
  currentRight = 0;
  digitalWrite(STBY, HIGH);
  // Set both direction pairs to short-brake BEFORE re-enabling PWM.
  // Otherwise there can be a momentary full-power drive pulse.
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, HIGH);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, HIGH);
  analogWrite(PWMA, 255);
  analogWrite(PWMB, 255);
  driveState = state;
  lastMotionCommand = millis();
}

void legacyMotion() {
  commandWheels(legacyLeftDir * legacySpeed, legacyRightDir * legacySpeed);
}

void legacyByte(char value) {
  switch (value) {
    case 'F': legacyLeftDir = 1; legacyRightDir = 1; legacyMotion(); break;
    case 'B': legacyLeftDir = -1; legacyRightDir = -1; legacyMotion(); break;
    case 'L': legacyLeftDir = -1; legacyRightDir = 1; legacyMotion(); break;
    case 'R': legacyLeftDir = 1; legacyRightDir = -1; legacyMotion(); break;
    case 'S': legacyLeftDir = 0; legacyRightDir = 0; commandWheels(0, 0); break;
    case 'K': activeBrake(); break;
    case 'Q': handshakePending = true; Serial.println(F("H,13")); break;
    case '1': legacySpeed = 110; legacyMotion(); break;
    case '2': legacySpeed = 150; legacyMotion(); break;
    case '3': legacySpeed = 205; legacyMotion(); break;
    case '4': legacySpeed = 255; legacyMotion(); break;
  }
}

bool parseSignedInt(const char* s) {
  if (*s == '-' || *s == '+') ++s;
  if (*s < '0' || *s > '9') return false;
  while (*s >= '0' && *s <= '9') ++s;
  return *s == '\0';
}

void processPacket(char* line) {
  if (line[0] != 'M' || line[1] != ',') return;
  char* comma = strchr(line + 2, ',');
  if (!comma) return;
  *comma = '\0';
  const char* leftText = line + 2;
  const char* rightText = comma + 1;
  if (!parseSignedInt(leftText) || !parseSignedInt(rightText)) return;
  if (strlen(leftText) > 4 || strlen(rightText) > 4) return;
  int left = atoi(leftText);
  int right = atoi(rightText);
  if (left < -255 || left > 255 || right < -255 || right > 255) return;
  // A stale held-key stream must never re-start motors after a watchdog stop.
  // A deliberate stop (K or M,0,0) clears lockout; next new key press may drive.
  if (watchdogLockout && (left != 0 || right != 0)) return;
  if (left == 0 && right == 0) watchdogLockout = false;
  commandWheels(left, right);
  ++acceptedDrivePackets;
}

void receiveByte(char value, bool usbDebug) {
  // Safety priority: K can never be part of a valid numeric M packet.
  // Accept it even if a previous M frame lost its newline or was truncated.
  if (value == 'K') {
    packetPos = 0;
    receivingPacket = false;
    watchdogLockout = false;
    activeBrake();
    return;
  }
  // If a packet is interrupted, a fresh M can resync without requiring reset.
  // M is not valid inside a signed numeric motor payload.
  if (receivingPacket && value == 'M') {
    packet[0] = 'M';
    packetPos = 1;
    return;
  }
  if (receivingPacket) {
    if (value == '\n' || value == '\r') {
      packet[packetPos] = '\0';
      processPacket(packet);
      packetPos = 0;
      receivingPacket = false;
    } else if (packetPos < sizeof(packet) - 1) {
      packet[packetPos++] = value;
    } else {
      // Drop malformed long packets rather than executing truncated commands.
      packetPos = 0;
      receivingPacket = false;
    }
  } else if (value == 'M') {
    receivingPacket = true;
    packet[0] = 'M';
    packetPos = 1;
  } else if (value == 'Q') {
    // Never send SoftwareSerial output while a motor packet is arriving.
    handshakePending = true;
    Serial.println(F("H,13"));
  } else if (usbDebug) {
    // Legacy single-byte drive commands are intentionally USB-only.
    // Noise/corrupt BLE bytes must never start the motor.
    legacyByte(value);
  }
}

void sendTelemetry() {
  // One short write limits SoftwareSerial transmit time. Telemetry describes
  // the Arduino's commanded PWM, not actual motor rotation or battery level.
  char frame[48];
  int n = snprintf(frame, sizeof(frame), "T,%d,%d,%c,%u,%lu\n",
                   currentLeft, currentRight, driveState, telemetrySeq,
                   acceptedDrivePackets);
  if (n > 0 && n < (int)sizeof(frame)) {
    BT.write((const uint8_t*)frame, (size_t)n);
    telemetrySeq = (telemetrySeq + 1) % 1000;
  }
}

void setup() {
  pinMode(STBY, OUTPUT);
  digitalWrite(STBY, LOW);
  pinMode(PWMA, OUTPUT);
  pinMode(PWMB, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);
  // No coast-on-boot: arm the hardware short brake before enabling STBY.
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, HIGH);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, HIGH);
  analogWrite(PWMA, 255);
  analogWrite(PWMB, 255);
  driveState = 'B';
  currentLeft = currentRight = 0;
  lastMotionCommand = millis();
  Serial.begin(9600);
  BT.begin(9600);
  digitalWrite(STBY, HIGH);
  Serial.println(F("BUGGY v1.6.4 READY / M,left,right / K brake"));
}

void loop() {
  // Consume incoming motor commands before doing any outgoing UART work.
  // Update lastRxByteAt for every byte (including packet fragments).
  while (BT.available() > 0) {
    char incoming = (char)BT.read();
    lastRxByteAt = millis();
    receiveByte(incoming, false);
  }
  while (Serial.available() > 0) receiveByte((char)Serial.read(), true);

  if (receivingPacket && millis() - lastRxByteAt > PACKET_TIMEOUT_MS) {
    receivingPacket = false;
    packetPos = 0;
  }

  if ((currentLeft != 0 || currentRight != 0) &&
      (millis() - lastMotionCommand > WATCHDOG_MS)) {
    activeBrake('W');  // Active brake if BLE commands stop unexpectedly.
    watchdogLockout = true;  // require a fresh release before more motion
    Serial.println(F("WATCHDOG ACTIVE BRAKE"));
  }

  // SoftwareSerial cannot receive while transmitting. A deferred handshake
  // goes ahead of periodic telemetry but only after a quiet UART gap.
  if (!receivingPacket && BT.available() == 0 &&
      (TELEMETRY_WHILE_MOVING || (currentLeft == 0 && currentRight == 0)) &&
      millis() - lastRxByteAt >= RX_QUIET_MS) {
    if (handshakePending) {
      handshakePending = false;
      BT.println(F("H,13"));
    } else if (millis() - lastTelemetry >= TELEMETRY_MS &&
               (TELEMETRY_WHILE_MOVING || (currentLeft == 0 && currentRight == 0))) {
      lastTelemetry = millis();
      sendTelemetry();
    }
  }
}
