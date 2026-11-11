/*
  Buggy Motor Test v1.6.5 — standalone Arduino Uno sketch.
  SAFETY: wheels lifted, motor battery disconnected during upload, and
  physical battery cut-off reachable. Tests are NOT run on power-up.
  Serial Monitor: 9600 baud; send T to start, X or S to abort immediately.
  Drives each channel at low PWM, independently in both directions.
  This is an OPEN-LOOP test: it does not confirm actual wheel speed.
*/
const byte STBY=4, PWMA=5, PWMB=6, AIN1=7, AIN2=8, BIN1=9, BIN2=10;
const int TEST_PWM=160;
const unsigned long RUN_MS=650, GAP_MS=600;
bool running=false;
bool inGap=false;
byte step=0;
unsigned long phaseAt=0;

void brake() {
  analogWrite(PWMA,0); analogWrite(PWMB,0);
  digitalWrite(AIN1,HIGH); digitalWrite(AIN2,HIGH);
  digitalWrite(BIN1,HIGH); digitalWrite(BIN2,HIGH);
  analogWrite(PWMA,255); analogWrite(PWMB,255);
}
void channelDirection(byte a,byte b,int value) {
  digitalWrite(a, value>=0 ? HIGH:LOW);
  digitalWrite(b, value>0 ? LOW:HIGH);
}
void wheels(int left,int right) {
  analogWrite(PWMA,0); analogWrite(PWMB,0);
  channelDirection(AIN1,AIN2,left);
  channelDirection(BIN1,BIN2,right);
  analogWrite(PWMA,left==0 ? 255 : abs(left));
  analogWrite(PWMB,right==0 ? 255 : abs(right));
}
void startStep(byte n) {
  switch(n) {
    case 0: Serial.println(F("1/6 LEFT FORWARD"));  wheels(TEST_PWM,0); break;
    case 1: Serial.println(F("2/6 LEFT REVERSE"));  wheels(-TEST_PWM,0); break;
    case 2: Serial.println(F("3/6 RIGHT FORWARD")); wheels(0,TEST_PWM); break;
    case 3: Serial.println(F("4/6 RIGHT REVERSE")); wheels(0,-TEST_PWM); break;
    case 4: Serial.println(F("5/6 BOTH FORWARD"));  wheels(TEST_PWM,TEST_PWM); break;
    case 5: Serial.println(F("6/6 BOTH REVERSE"));  wheels(-TEST_PWM,-TEST_PWM); break;
  }
  phaseAt=millis();
}
void abortTest() {
  brake(); running=false; inGap=false;
  Serial.println(F("STOPPED / BRAKED"));
}
void setup() {
  pinMode(STBY,OUTPUT); digitalWrite(STBY,LOW);
  pinMode(PWMA,OUTPUT); pinMode(PWMB,OUTPUT);
  pinMode(AIN1,OUTPUT); pinMode(AIN2,OUTPUT);
  pinMode(BIN1,OUTPUT); pinMode(BIN2,OUTPUT);
  brake();
  Serial.begin(9600);
  digitalWrite(STBY,HIGH);
  Serial.println(F("WHEELS UP + MOTOR SWITCH READY? Send T, X/S abort."));
}
void loop() {
  // Always poll abort commands, even while a test is underway.
  while (Serial.available()) {
    char c=(char)Serial.read();
    if(c=='X'||c=='x'||c=='S'||c=='s') { abortTest(); }
    else if((c == 'T'||c == 't')&&!running) {
      step=0; running=true; inGap=false;
      startStep(step);
    }
  }
  if(!running) return;
  if(!inGap && millis()-phaseAt>=RUN_MS) {
    brake(); inGap=true; phaseAt=millis();
  } else if(inGap && millis()-phaseAt>=GAP_MS) {
    ++step;
    if(step>=6) {
      abortTest();
      Serial.println(F("COMPLETE: compare actual wheel direction with labels."));
    } else {
      inGap=false;
      startStep(step);
    }
  }
}
