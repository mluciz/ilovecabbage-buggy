#include "SoftwareSerial.h"
#include <cassert>
#include <iostream>
unsigned long mock_millis = 0;
std::array<int, 16> pin_digital{};
std::array<int, 16> pin_pwm{};
MockPort Serial;
#include "../../arduino/BuggyController/BuggyController.ino"

void send(const std::string& command) {
    BT.inject(command);
    mock_millis += 5;
    loop();
}
void assert_braked() {
    assert(pin_digital[4] == HIGH);
    assert(pin_digital[7] == HIGH && pin_digital[8] == HIGH);
    assert(pin_digital[9] == HIGH && pin_digital[10] == HIGH);
    assert(pin_pwm[5] == 255 && pin_pwm[6] == 255);
}
int main() {
    setup();
    assert_braked();
    assert(currentLeft == 0 && currentRight == 0);
    send("M,120,120\n");
    assert(currentLeft == 120 && currentRight == 120 && driveState == 'D');
    assert(pin_pwm[5] == 120 && pin_pwm[6] == 120);
    assert(pin_digital[7] == HIGH && pin_digital[8] == LOW);
    assert(pin_digital[9] == HIGH && pin_digital[10] == LOW);
    // Ten seconds of valid refreshed commands must never trip the watchdog.
    for (int i = 0; i < 85; ++i) {
        mock_millis += 115;
        send("M,120,120\n");
        assert(driveState == 'D');
    }
    send("M,-200,-200\n");
    assert(currentLeft == -200 && currentRight == -200 && driveState == 'D');
    assert(pin_pwm[5] == 200 && pin_pwm[6] == 200);
    assert(pin_digital[7] == LOW && pin_digital[8] == HIGH);
    assert(pin_digital[9] == LOW && pin_digital[10] == HIGH);
    send("K\n");
    assert_braked();
    assert(currentLeft == 0 && currentRight == 0);
    send("M,25"); // incomplete UART frame should not swallow emergency braking
    send("K\n");
    assert_braked();
    send("F"); // Unframed legacy motion over BLE must not start a wheel.
    assert_braked();
    send("M,120,90\n");
    assert(currentLeft == 120 && currentRight == 90);
    mock_millis += 1201;
    loop();
    assert_braked();
    assert(driveState == 'W' && watchdogLockout);
    send("M,200,200\n");
    assert_braked();  // no uncommanded restart after watchdog
    send("K\n");
    assert(!watchdogLockout);
    send("M,2");
    mock_millis += 200;
    loop();
    send("M,0,190\n");
    assert(currentLeft == 0 && currentRight == 190); // independent right drive
    assert(pin_pwm[5] == 255 && pin_pwm[6] == 190);
    assert(pin_digital[7] == HIGH && pin_digital[8] == HIGH);
    // Never transmit SoftwareSerial telemetry while a wheel is moving:
    // a half-duplex transmission can silently swallow an incoming motor packet.
    BT.output.clear();
    mock_millis += 1100;
    loop();
    assert(BT.output.find("T,") == std::string::npos);
    send("K\n");
    mock_millis += RX_QUIET_MS + 1;
    loop();
    assert(BT.output.find("T,0,0,B,") != std::string::npos);
    // The optional sixth telemetry field is the accepted motor-frame count.
    assert(acceptedDrivePackets >= 85);
    // Handshake replies wait for a quiet interval; they must not transmit
    // during an incoming UART packet and cause SoftwareSerial to miss data.
    BT.output.clear();
    send("Q\n");
    assert(handshakePending);
    assert(BT.output.find("H,13") == std::string::npos);
    mock_millis += RX_QUIET_MS + 1;
    loop();
    assert(!handshakePending);
    assert(BT.output.find("H,13") != std::string::npos);
    send("M,120,120\n");
    assert(currentLeft == 120);
    mock_millis += WATCHDOG_MS + 1;
    loop();
    assert_braked();
    assert(driveState == 'W' && watchdogLockout);
    send("M,255,255\n");
    assert_braked();  // stale drive stream must not auto-restart after watchdog
    assert(watchdogLockout);
    send("K\n");
    assert(!watchdogLockout);
    send("M,80,-80\n");
    assert(currentLeft == 80 && currentRight == -80);
    send("M,0,0\n");
    assert_braked();
    std::cout << "firmware simulation: startup, directions, brake, telemetry suppression, command counter, watchdog lockout PASS\n";
}
