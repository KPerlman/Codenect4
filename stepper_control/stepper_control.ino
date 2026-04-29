#include <AccelStepper.h>
#include <SoftwareSerial.h>

#define DIR_PIN 2
#define STEP_PIN 3
#define EN_PIN 4

SoftwareSerial PiSerial(10, 11); // RX, TX

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

long liftDistance = 3000;
bool waitingRelease = false;

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
  if (PiSerial.available() > 0) {
    String msg = PiSerial.readStringUntil('\n');
    msg.trim();

    if (msg.startsWith("SPEED ")) {
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
      stepper.move(steps);
      while (stepper.distanceToGo() != 0) {
        stepper.run();
      }
      PiSerial.println("DONE");
    } else if (msg.startsWith("MOVE")) {
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