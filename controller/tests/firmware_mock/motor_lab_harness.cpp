#include "SoftwareSerial.h"
#include <cassert>
#include <iostream>
unsigned long mock_millis = 0;
std::array<int, 16> pin_digital{};
std::array<int, 16> pin_pwm{};
MockPort Serial;
#include "../../arduino/MotorTest/MotorTest.ino"

void advance(unsigned long ms) { mock_millis += ms; loop(); }
void braked() {
    assert(pin_digital[4] == HIGH);
    assert(pin_digital[7] == HIGH && pin_digital[8] == HIGH);
    assert(pin_digital[9] == HIGH && pin_digital[10] == HIGH);
    assert(pin_pwm[5] == 255 && pin_pwm[6] == 255);
}
int main() {
    setup();
    braked();
    auto old_time = mock_millis;
    loop();
    assert(old_time == mock_millis); // startup cannot drive without T
    Serial.inject("T");
    loop();
    assert(running && !inGap && step == 0);
    assert(pin_pwm[5] == TEST_PWM && pin_pwm[6] == 255);

    // The first run can be cancelled immediately even during motor activity.
    Serial.inject("X");
    loop();
    assert(!running);
    braked();
    advance(5000);
    braked();

    // Re-run and inspect every motor phase and each braking interval.
    Serial.inject("T");
    loop();
    for(int n=0; n<6; ++n) {
        assert(step == n && running && !inGap);
        if(n == 0) assert(pin_pwm[5] == TEST_PWM && pin_pwm[6] == 255);
        if(n == 1) assert(pin_pwm[5] == TEST_PWM && pin_pwm[6] == 255);
        if(n == 2) assert(pin_pwm[5] == 255 && pin_pwm[6] == TEST_PWM);
        if(n == 3) assert(pin_pwm[5] == 255 && pin_pwm[6] == TEST_PWM);
        if(n >= 4) assert(pin_pwm[5] == TEST_PWM && pin_pwm[6] == TEST_PWM);
        advance(RUN_MS);
        braked();
        assert(inGap);
        advance(GAP_MS);
    }
    assert(!running && step == 6);
    braked();
    assert(Serial.output.find("LEFT REVERSE") != std::string::npos);
    assert(Serial.output.find("RIGHT REVERSE") != std::string::npos);
    assert(Serial.output.find("COMPLETE") != std::string::npos);
    std::cout << "motor lab: startup, independent direction channels, abort and six braking gaps PASS\n";
}
