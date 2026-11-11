#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>
#include <array>
#include <algorithm>

using byte = unsigned char;
#define OUTPUT 1
#define HIGH 1
#define LOW 0
#define F(s) s
#define constrain(x,a,b) std::max((a),std::min((b),(x)))
extern unsigned long mock_millis;
extern std::array<int, 16> pin_digital;
extern std::array<int, 16> pin_pwm;
inline unsigned long millis() { return mock_millis; }
inline void pinMode(byte, byte) { }
inline void digitalWrite(byte pin, int value) { pin_digital.at(pin) = value; }
inline void analogWrite(byte pin, int value) { pin_pwm.at(pin) = value; }

class MockPort {
public:
    std::deque<char> input;
    std::string output;
    void begin(int) { }
    int available() const { return (int)input.size(); }
    int read() { int c = input.front(); input.pop_front(); return c; }
    void inject(const std::string& text) { for(char c:text) input.push_back(c); }
    void print(const char* s) { output += s; }
    void print(int n) { output += std::to_string(n); }
    void println(const char* s) { output += s; output += "\n"; }
    void println(int n) { output += std::to_string(n); output += "\n"; }
    size_t write(const uint8_t* b, size_t n) { output.append((const char*)b, n); return n; }
};
class SoftwareSerial : public MockPort {
public:
    SoftwareSerial(int, int) { }
};
extern MockPort Serial;
