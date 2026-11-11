#include "SoftwareSerial.h"
#include <cassert>
#include <iostream>
using __FlashStringHelper = char;
unsigned long mock_millis = 0;
std::array<int, 16> pin_digital{};
std::array<int, 16> pin_pwm{};
MockPort Serial;
inline void delay(unsigned long time_ms) { mock_millis += time_ms; }
#include "../../arduino/MotorTest/MotorTest.ino"
int main() {
    setup();
    assert(pin_digital[4] == HIGH);
    assert(pin_digital[7] == HIGH && pin_digital[8] == HIGH);
    assert(pin_digital[9] == HIGH && pin_digital[10] == HIGH);
    assert(pin_pwm[5] == 255 && pin_pwm[6] == 255);
    auto before = mock_millis;
    loop();  // no 'T' command: must not run a test
    assert(mock_millis == before);
    Serial.inject("T");
    loop();
    assert(Serial.output.find("RIGHT REVERSE") != std::string::npos);
    assert(Serial.output.find("LEFT REVERSE") != std::string::npos);
    assert(Serial.output.find("COMPLETE / ACTIVE BRAKE") != std::string::npos);
    assert(pin_pwm[5] == 255 && pin_pwm[6] == 255);
    assert(pin_digital[7] == HIGH && pin_digital[8] == HIGH);
    assert(pin_digital[9] == HIGH && pin_digital[10] == HIGH);
    std::cout << "motor lab safe startup and explicit-run test PASS\n";
}
