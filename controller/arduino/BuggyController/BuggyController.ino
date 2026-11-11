#include <SoftwareSerial.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/*
  BUGGY CONTROL CENTER v1.6.5-safety (derived from verified v1.6.4)
  Arduino Uno + TB6612FNG + HM-10 at 9600 baud

  Pins are unchanged from v1.1:
  D4 STBY, D5 PWMA, D6 PWMB, D7 AIN1, D8 AIN2, D9 BIN1, D10 BIN2
  D2 RX from HM-10 TX, D3 TX to HM-10 RX via 3.3 V logic-level divider

  Incoming BLE/USB commands (only framed M packets drive via BLE):
    M,<left>,<right>\n   Signed PWM (-255..255), 0,0 = ACTIVE BRAKE
    K\n                 Brake / clear watchdog lockout (existing app behaviour)
    Q\n                 Safe firmware handshake: replies H,13\n    X\n                 Latching emergency stop (needs U after physical inspection)
    U\n                 Release X latch only; still needs M,0,0 to drive
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
// Brake both channels briefly before reversing either wheel. Non-blocking:
// incoming stop commands remain responsive during the pause.
const unsigned long REVERSAL_BRAKE_MS = 70;
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

struct FrameBuffer {
  char packet[24];
  byte pos;
  bool receiving;
  unsigned long lastByteAt;
};
FrameBuffer bleFrame = {};
FrameBuffer usbFrame = {};
bool handshakePending = false;
bool eStopLatched = false;
bool reversalPending = false;
int pendingLeft = 0;
int pendingRight = 0;
unsigned long reversalStartedAt = 0;

void activeBrake(char state = 'B');

// Pause BOTH channels before applying either direction. This prevents the
// left and right motors from briefly driving conflicting command generations.
void applyWheels(int left, int right) {
  const int l = constrain(left * LEFT_MOTOR_POLARITY, -255, 255);
  const int r = constrain(right * RIGHT_MOTOR_POLARITY, -255, 255);
  analogWrite(PWMA, 0);
  analogWrite(PWMB, 0);
  digitalWrite(AIN1, l >= 0 ? HIGH : LOW);
  digitalWrite(AIN2, l > 0 ? LOW : HIGH);
  digitalWrite(BIN1, r >= 0 ? HIGH : LOW);
  digitalWrite(BIN2, r > 0 ? LOW : HIGH);
  // A stationary wheel must short-brake, not coast.
  analogWrite(PWMA, l == 0 ? 255 : abs(l));
  analogWrite(PWMB, r == 0 ? 255 : abs(r));
  currentLeft = left;
  currentRight = right;
  driveState = (left || right) ? 'D' : 'B';
}

bool reverses(int now, int next) {
  return (now > 0 && next < 0) || (now < 0 && next > 0);
}

void commandWheels(int left, int right) {
  left = constrain(left, -255, 255);
  right = constrain(right, -255, 255);
  if (left == 0 && right == 0) {
    activeBrake();
    return;
  }
  if (eStopLatched || watchdogLockout) return;
  lastMotionCommand = millis();
  if (reversalPending) {
    // A stop arriving during deadtime cancels this pending request.
    // Repeated commands do NOT restart the delay forever.
    pendingLeft = left;
    pendingRight = right;
    return;
  }
  if (reverses(currentLeft, left) || reverses(currentRight, right)) {
    activeBrake();
    pendingLeft = left;
    pendingRight = right;
    reversalPending = true;
    reversalStartedAt = millis();
    return;
  }
  applyWheels(left, right);
}

void activeBrake(char state) {
  reversalPending = false;
  currentLeft = currentRight = 0;
  // Remove PWM before switching both direction pairs to SHORT BRAKE.
  analogWrite(PWMA, 0);
  analogWrite(PWMB, 0);
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, HIGH);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, HIGH);
  analogWrite(PWMA, 255);
  analogWrite(PWMB, 255);
  digitalWrite(STBY, HIGH);
  driveState = state;
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
  if (left == 0 && right == 0) {
    // A deliberate zero frame clears the ordinary watchdog/brake lockout.
    // It never clears the latched emergency stop.
    watchdogLockout = false;
  }
  if (!eStopLatched && !watchdogLockout) {
    commandWheels(left, right);
    ++acceptedDrivePackets;
  }
}

void receiveByte(char value, FrameBuffer &frame, bool usbDebug) {
  frame.lastByteAt = millis();
  // Emergency commands preempt even damaged or incomplete motor frames.
  if (value == 'X') {
    frame.pos = 0; frame.receiving = false;
    eStopLatched = true;
    watchdogLockout = true;
    activeBrake('E');
    return;
  }
  if (value == 'K') {
    frame.pos = 0; frame.receiving = false;
    // Preserve existing v1.6.4 app compatibility: K is an ordinary
    // active brake / watchdog-rearm command. Only X is a latched E-stop.
    watchdogLockout = false;
    activeBrake();
    return;
  }
  if (frame.receiving && value == 'M') {
    // Framing recovery for a missing newline; M is never a numeric field.
    frame.packet[0] = 'M';
    frame.pos = 1;
    return;
  }
  if (frame.receiving) {
    if (value == '\n' || value == '\r') {
      frame.packet[frame.pos] = '\0';
      processPacket(frame.packet);
      frame.pos = 0;
      frame.receiving = false;
    } else if (frame.pos < sizeof(frame.packet) - 1) {
      frame.packet[frame.pos++] = value;
    } else {
      frame.pos = 0;
      frame.receiving = false;
    }
  } else if (value == 'M') {
    frame.receiving = true;
    frame.packet[0] = 'M';
    frame.pos = 1;
  } else if (value == 'U') {
    // Never allow a raw U to resume motors: a zero frame is still required.
    eStopLatched = false;
    watchdogLockout = true;
    activeBrake();
  } else if (value == 'Q') {
    handshakePending = true;
    Serial.println(F("H,13"));
  } else if (usbDebug && !eStopLatched) {
    // Legacy drive bytes remain local USB only.
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
  Serial.println(F("BUGGY v1.6.5-safety READY / M,left,right / K brake / X latch"));
}

void loop() {
  while (BT.available() > 0) receiveByte((char)BT.read(), bleFrame, false);
  while (Serial.available() > 0) receiveByte((char)Serial.read(), usbFrame, true);

  if (bleFrame.receiving &&
      millis() - bleFrame.lastByteAt > PACKET_TIMEOUT_MS) {
    bleFrame.receiving = false; bleFrame.pos = 0;
  }
  if (usbFrame.receiving &&
      millis() - usbFrame.lastByteAt > PACKET_TIMEOUT_MS) {
    usbFrame.receiving = false; usbFrame.pos = 0;
  }

  if ((currentLeft || currentRight || reversalPending) &&
      millis() - lastMotionCommand > WATCHDOG_MS) {
    activeBrake('W');
    watchdogLockout = true;
    Serial.println(F("WATCHDOG ACTIVE BRAKE"));
  }

  if (reversalPending && !eStopLatched && !watchdogLockout &&
      millis() - reversalStartedAt >= REVERSAL_BRAKE_MS) {
    reversalPending = false;
    applyWheels(pendingLeft, pendingRight);
  }

  // SoftwareSerial TX can drop incoming bytes; only report while braked,
  // after the receive buffer has been quiet for a generous gap.
  if (!bleFrame.receiving && BT.available() == 0 &&
      (TELEMETRY_WHILE_MOVING || (currentLeft == 0 && currentRight == 0)) &&
      millis() - bleFrame.lastByteAt >= RX_QUIET_MS) {
    if (handshakePending) {
      handshakePending = false;
      BT.println(F("H,13"));
    } else if (millis() - lastTelemetry >= TELEMETRY_MS) {
      lastTelemetry = millis();
      sendTelemetry();
    }
  }
}
