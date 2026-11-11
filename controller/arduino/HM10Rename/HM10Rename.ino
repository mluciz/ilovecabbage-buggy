/*
  HM-10 ONE-TIME BLUETOOTH NAME SETUP (Arduino Uno).
  This is NOT the drive firmware. It keeps TB6612FNG disabled.
  HM-10 UART wiring: D2 <- HM10 TXD; D3 -> HM10 RXD through 3.3V level shift.
  9600 baud, Serial Monitor set to 9600 baud.
  Send R to TRY the exact 16-character name "cabbagelover1000".
  Most genuine HM-10 firmware supports at most 12 characters. The module
  may reject or truncate the exact name. Read the response; do not assume it
  worked. Send S for the supported fallback "cabbage1000".
  Send Q to query current name. Send T to test UART with plain AT.
  Module must be unconnected over BLE for normal local AT command mode.
  No AT command is sent automatically at startup.
  Disconnect MOTOR BATTERY during upload and configuration.
  Re-upload BuggyController.ino before using the desktop WASD app.
*/
#include <SoftwareSerial.h>
SoftwareSerial HM10(2, 3);
const char DESIRED_NAME[] = "cabbagelover1000";
const char SAFE_NAME[] = "cabbage1000";

void sendCommand(const char* command) {
  // Standard HM-10 AT interface usually uses NO line ending.
  HM10.print(command);
  Serial.print(F("SENT: "));
  Serial.println(command);
  Serial.println(F("Check the HM-10 response below. Absence of OK is NOT success."));
}

void setup() {
  // Hardware enable must be LOW throughout the rename procedure.
  pinMode(4, OUTPUT);
  digitalWrite(4, LOW); // TB6612 STBY disabled
  pinMode(5, OUTPUT);
  pinMode(6, OUTPUT);
  digitalWrite(5, LOW);
  digitalWrite(6, LOW);
  Serial.begin(9600);
  HM10.begin(9600);
  Serial.println(F("HM-10 NAME SETUP. MOTOR DRIVER DISABLED."));
  Serial.println(F("Disconnect the motor battery. Disconnect other BLE clients."));
  Serial.println(F("R = try cabbagelover1000 (16 chars; HM-10 often rejects)"));
  Serial.println(F("S = set cabbage1000 (11-char compatible fallback)"));
  Serial.println(F("Q = query name; T = AT connection test"));
  Serial.println(F("Select 9600 baud; any Serial Monitor line ending works."));
}

void loop() {
  while (Serial.available()) {
    const char c = (char)Serial.read();
    if (c == 'R' || c == 'r') {
      sendCommand("AT+NAMEcabbagelover1000");
    } else if (c == 'S' || c == 's') {
      sendCommand("AT+NAMEcabbage1000");
    } else if (c == 'Q' || c == 'q') {
      sendCommand("AT+NAME?");
    } else if (c == 'T' || c == 't') {
      sendCommand("AT");
    }
  }
  while (HM10.available()) {
    Serial.write(HM10.read());
  }
}
