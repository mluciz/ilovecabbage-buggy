/*
  BUGGY MOTOR CHANNEL LAB v1.6.3 — NO BLUETOOTH REQUIRED.

  SAFETY:
  - MOTOR BATTERY OFF while uploading; wheels raised for the entire test.
  - Arduino Uno to TB6612FNG wiring: D4 STBY, D5 PWMA, D6 PWMB,
    D7 AIN1, D8 AIN2, D9 BIN1, D10 BIN2.
  - Motor VM is powered separately, with a shared GND and a physical switch.
  - Starts in ACTIVE SHORT BRAKE, NEVER drives automatically on upload/reset.
  - Open USB Serial Monitor at 9600, type T + Send to run each test ONCE.
  - Cut battery power immediately if a wheel turns without a command.

  Sequence: LEFT FORWARD, LEFT REVERSE, RIGHT FORWARD, RIGHT REVERSE,
            BOTH FORWARD, BOTH REVERSE, then ACTIVE BRAKE.
  Right-only reverse is included to diagnose the previously reported fault.
*/
const byte STBY = 4;
const byte PWMA = 5;
const byte PWMB = 6;
const byte AIN1 = 7;
const byte AIN2 = 8;
const byte BIN1 = 9;
const byte BIN2 = 10;
const int TEST_PWM = 220;

void brake() {
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, HIGH);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, HIGH);
  analogWrite(PWMA, 255);
  analogWrite(PWMB, 255);
}
void channel(byte pwm, byte in1, byte in2, int speed) {
  analogWrite(pwm, 0);
  if (speed == 0) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, HIGH);
    analogWrite(pwm, 255);
    return;
  }
  digitalWrite(in1, speed > 0 ? HIGH : LOW);
  digitalWrite(in2, speed < 0 ? HIGH : LOW);
  analogWrite(pwm, abs(speed));
}
void wheels(int left, int right) {
  channel(PWMA, AIN1, AIN2, left);
  channel(PWMB, BIN1, BIN2, right);
}
void test(const __FlashStringHelper* name, int left, int right) {
  brake();
  delay(500);
  Serial.println(name);
  wheels(left, right);
  delay(1200);
  brake();
  delay(1000);
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
  brake();
  Serial.begin(9600);
  digitalWrite(STBY, HIGH);  // Enable only after both channels have brake pins.
  Serial.println(F("MOTOR CHANNEL LAB READY / BRAKED"));
  Serial.println(F("Raise wheels; send T to run 6 short tests."));
}
void loop() {
  if (Serial.available()) {
    const char c = (char)Serial.read();
    if (c == 'T' || c == 't') {
      Serial.println(F("TEST START — CUT MOTOR POWER IF UNEXPECTED MOTION"));
      test(F("1 LEFT FORWARD"), TEST_PWM, 0);
      test(F("2 LEFT REVERSE"), -TEST_PWM, 0);
      test(F("3 RIGHT FORWARD"), 0, TEST_PWM);
      test(F("4 RIGHT REVERSE"), 0, -TEST_PWM);
      test(F("5 BOTH FORWARD"), TEST_PWM, TEST_PWM);
      test(F("6 BOTH REVERSE"), -TEST_PWM, -TEST_PWM);
      brake();
      Serial.println(F("COMPLETE / ACTIVE BRAKE / SEND T TO REPEAT"));
    }
  }
}
