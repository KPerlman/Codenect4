#include <AccelStepper.h>

#define DIR_PIN 2
#define STEP_PIN 3
#define EN_PIN 4

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

long liftDistance = 3000; 

bool waitingRelease = false;

void setup() {
  Serial.begin(9600);
  
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, HIGH); 
  
  stepper.setMaxSpeed(1500);
  stepper.setAcceleration(800);
}

void loop() {
  if (Serial.available() > 0) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();

    if (msg.startsWith("MOVE")) {
      stepper.move(liftDistance);
      while (stepper.distanceToGo() != 0) {
        stepper.run();
      }

      waitingRelease = true;
      Serial.println("ARRIVED");
    } else if (msg == "RELEASE" && waitingRelease) {
      stepper.move(-liftDistance);
      while (stepper.distanceToGo() != 0) {
        stepper.run();
      }
      waitingRelease = false;
      Serial.println("DONE");
    }
  }
}