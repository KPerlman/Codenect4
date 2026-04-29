#include <AccelStepper.h>
#include <SoftwareSerial.h>

#define DIR_PIN 2
#define STEP_PIN 3
#define EN_PIN 4

SoftwareSerial PiSerial(8, 9); // RX, TX

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

long liftDistance = 3000;
bool waitingRelease = false;
bool runContinuous = false;

long parseValue(const String &msg, int prefixLen) {
  String value = msg.substring(prefixLen);
  value.trim();
  return value.toInt();
}

void setup() {
  Serial.begin(115200);   // USB debug
  PiSerial.begin(9600);   // Pi UART

  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);

  stepper.setMaxSpeed(1500);
  stepper.setAcceleration(800);
}

void loop() {
  if (runContinuous) {
    stepper.runSpeed();
  }
  if (PiSerial.available() > 0) {
    String msg = PiSerial.readStringUntil('\n');
    msg.trim();

    if (msg == "PING") {
      PiSerial.println("PONG");
      Serial.println("PONG");
    } else if (msg.startsWith("ECHO ")) {
      String payload = msg.substring(5);
      PiSerial.println(payload);
      Serial.println(payload);
    } else if (msg.startsWith("RUN ")) {
      long speed = parseValue(msg, 4);
      if (speed != 0) {
        runContinuous = true;
        stepper.setSpeed(speed);
        PiSerial.println("OK");
      } else {
        PiSerial.println("ERR");
      }
    } else if (msg == "STOP") {
      runContinuous = false;
      stepper.setSpeed(0);
      PiSerial.println("OK");
    } else if (msg.startsWith("SPEED ")) {
      long speed = parseValue(msg, 6);
      if (speed > 0) {
        stepper.setMaxSpeed(speed);
        PiSerial.println("OK");
      } else {
        PiSerial.println("ERR");
      }
    } else if (msg.startsWith("ACCEL ")) {
      long accel = parseValue(msg, 6);
      if (accel > 0) {
        stepper.setAcceleration(accel);
        PiSerial.println("OK");
      } else {
        PiSerial.println("ERR");
      }
    } else if (msg.startsWith("SETDIST ")) {
      long dist = parseValue(msg, 8);
      liftDistance = dist;
      PiSerial.println("OK");
    } else if (msg.startsWith("STEPS ")) {
      long steps = parseValue(msg, 6);
      runContinuous = false;
      stepper.move(steps);
      while (stepper.distanceToGo() != 0) {
        stepper.run();
      }
      PiSerial.println("DONE");
    } else if (msg.startsWith("MOVE")) {
      runContinuous = false;
      stepper.move(liftDistance);
      while (stepper.distanceToGo() != 0) {
        stepper.run();
      }
      waitingRelease = true;
      PiSerial.println("ARRIVED");
    } else if (msg == "RELEASE" && waitingRelease) {
      stepper.move(-liftDistance);
      while (stepper.distanceToGo() != 0) {
        stepper.run();
      }
      waitingRelease = false;
      PiSerial.println("DONE");
    }
  }
}