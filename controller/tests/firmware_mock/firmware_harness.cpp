#include "SoftwareSerial.h"
#include <cassert>
#include <iostream>
unsigned long mock_millis = 0;
std::array<int, 16> pin_digital{};
std::array<int, 16> pin_pwm{};
MockPort Serial;
#include "../../arduino/BuggyController/BuggyController.ino"

void advance(unsigned long ms) { mock_millis += ms; loop(); }
void ble(const std::string& command) { BT.inject(command); advance(5); }
void usb(const std::string& command) { Serial.inject(command); advance(5); }
void assert_braked() {
    assert(pin_digital[4] == HIGH);
    assert(pin_digital[7] == HIGH && pin_digital[8] == HIGH);
    assert(pin_digital[9] == HIGH && pin_digital[10] == HIGH);
    assert(pin_pwm[5] == 255 && pin_pwm[6] == 255);
    assert(currentLeft == 0 && currentRight == 0);
}
int main() {
    setup(); assert_braked();
    ble("M,120,120\n");
    assert(currentLeft == 120 && currentRight == 120 && driveState == 'D');
    assert(pin_pwm[5] == 120 && pin_pwm[6] == 120);
    assert(pin_digital[7] == HIGH && pin_digital[8] == LOW);
    assert(pin_digital[9] == HIGH && pin_digital[10] == LOW);

    // Refreshing a held key must not trip the 1200ms watchdog.
    for (int i = 0; i < 85; ++i) {
        advance(115);
        ble("M,120,120\n");
        assert(driveState == 'D');
    }

    // Direction reversal must brake BOTH wheels for at least 70ms.
    ble("M,-200,-200\n");
    assert_braked(); assert(reversalPending);
    advance(REVERSAL_BRAKE_MS - 1);
    assert_braked();
    advance(1);
    assert(currentLeft == -200 && currentRight == -200);
    assert(pin_digital[7] == LOW && pin_digital[8] == HIGH);
    assert(pin_digital[9] == LOW && pin_digital[10] == HIGH);
    assert(pin_pwm[5] == 200 && pin_pwm[6] == 200);

    // STOP must preempt a pending reversal without later replay.
    ble("M,200,200\n");
    assert(reversalPending);
    ble("K\n");
    assert_braked();
    assert(!reversalPending && !watchdogLockout);
    advance(REVERSAL_BRAKE_MS + 50);
    assert_braked();

    // v1.6.4 compatibility: K permits next nonzero M for old GUI.
    ble("M,120,90\n");
    assert(currentLeft == 120 && currentRight == 90);
    ble("M,0,0\n");
    assert_braked();

    // USB and BLE streams must NOT overwrite each other's fragmented M frame.
    ble("M,100,");
    usb("M,0,0\n");
    ble("70\n");
    assert(currentLeft == 100 && currentRight == 70);
    ble("K\n");

    // Incomplete/invalid frames must not drive a wheel.
    ble("M,9999,1\n");
    assert_braked();
    ble("M,150,");
    advance(PACKET_TIMEOUT_MS + 1);
    ble("150\n");
    assert_braked();
    ble("F");  // Legacy unframed BLE motion remains disabled.
    assert_braked();

    // Independent right channel, zero left = active short brake.
    ble("M,0,190\n");
    assert(currentLeft == 0 && currentRight == 190);
    assert(pin_pwm[5] == 255 && pin_pwm[6] == 190);
    assert(pin_digital[7] == HIGH && pin_digital[8] == HIGH);

    // Telemetry cannot interrupt active wheel commands.
    BT.output.clear();
    advance(TELEMETRY_MS + 100);
    assert(BT.output.find("T,") == std::string::npos);
    ble("K\n");
    advance(RX_QUIET_MS + 1);
    assert_braked();
    assert(BT.output.find("T,0,0,B,") != std::string::npos);
    assert(acceptedDrivePackets >= 85);

    // Watchdog blocks stale nonzero frames until deliberate K/zero release.
    ble("M,140,140\n");
    advance(WATCHDOG_MS + 1);
    assert_braked(); assert(watchdogLockout && driveState == 'W');
    ble("M,200,200\n");
    assert_braked();
    ble("K\n");
    assert(!watchdogLockout);
    ble("M,80,-80\n");
    assert(currentLeft == 80 && currentRight == -80);

    // Strong X E-stop must survive repeated K and zero packets.
    ble("X\n");
    assert_braked(); assert(eStopLatched && driveState == 'E');
    ble("K\n");
    assert(eStopLatched && driveState == 'E');
    ble("M,0,0\n");
    ble("M,200,200\n");
    assert_braked();
    ble("U\n");
    assert(!eStopLatched && watchdogLockout);
    ble("M,200,200\n");
    assert_braked();
    ble("M,0,0\n");
    ble("M,100,100\n");
    assert(currentLeft == 100 && currentRight == 100);

    // K remains preemptive within a damaged motor frame.
    ble("M,200,");
    ble("K");
    assert_braked();
    assert(!bleFrame.receiving);

    // Handshake defers until the RX line is idle and wheels braked.
    BT.output.clear();
    ble("Q\n");
    assert(handshakePending);
    advance(RX_QUIET_MS + 1);
    assert(!handshakePending);
    assert(BT.output.find("H,13") != std::string::npos);

    std::cout << "firmware simulation: parser isolation, reversal interlock, emergency latch, "
                 "watchdog, brake, channels and telemetry PASS\n";
}
