#pragma once
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <string>

using byte = unsigned char;
constexpr int OUTPUT=1, HIGH=1, LOW=0;
#define F(x) (x)

extern unsigned long simulatedMillis;
unsigned long millis();
void pinMode(byte pin, int mode);
void digitalWrite(byte pin, int value);
void analogWrite(byte pin, int value);
inline int constrain(int x, int low, int high) {
  return std::max(low, std::min(high, x));
}

struct FakeHardwareSerial {
  std::string rx;
  void begin(int) {}
  int available() const { return int(rx.size()); }
  int read() { int c=(unsigned char)rx.front(); rx.erase(0,1); return c; }
  template<class T> void println(const T&) {}
};
extern FakeHardwareSerial Serial;
