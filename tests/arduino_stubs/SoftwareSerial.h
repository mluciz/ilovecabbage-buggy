#pragma once
#include "Arduino.h"

class SoftwareSerial {
public:
  SoftwareSerial(int,int) {}
  std::string rx;
  std::string tx;
  void begin(int) {}
  int available() const { return int(rx.size()); }
  int read() { int c=(unsigned char)rx.front(); rx.erase(0,1); return c; }
  size_t write(const uint8_t* data, size_t n) {
    tx.append(reinterpret_cast<const char*>(data),n);
    return n;
  }
  void println(const char* value) { tx += value; tx += "\r\n"; }
};
