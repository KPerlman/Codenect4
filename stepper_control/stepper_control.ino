#include <AccelStepper.h>
#include <SoftwareSerial.h>

#define PRIMARY_DIR_PIN 2
#define PRIMARY_STEP_PIN 3
#define PRIMARY_EN_PIN 4

// Second TMC2209 for the board-clear gate.
// EN is hard-grounded on the driver, so only DIR/STEP are connected here.
#define GATE_DIR_PIN 5
#define GATE_STEP_PIN 6

SoftwareSerial PiSerial(8, 9); // RX, TX

AccelStepper primaryStepper(AccelStepper::DRIVER, PRIMARY_STEP_PIN, PRIMARY_DIR_PIN);
AccelStepper gateStepper(AccelStepper::DRIVER, GATE_STEP_PIN, GATE_DIR_PIN);

long liftDistance = 3000;
bool waitingRelease = false;
bool primaryRunContinuous = false;
bool gateRunContinuous = false;

long parseValue(const String &msg, int prefixLen) {
  String value = msg.substring(prefixLen);
  value.trim();
  return value.toInt();
}

void replyOk() {
  PiSerial.println("OK");
}

void replyErr() {
  PiSerial.println("ERR");
}

void runBlockingMove(AccelStepper &stepper, bool &runContinuous, long steps) {
  runContinuous = false;
  stepper.move(steps);
  while (stepper.distanceToGo() != 0) {
    stepper.run();
  }
}

bool handleRunCommand(AccelStepper &stepper, bool &runContinuous, long speed) {
  if (speed == 0) {
    replyErr();
    return false;
  }
  runContinuous = true;
  stepper.setSpeed(speed);
  replyOk();
  return true;
}

bool handleStopCommand(AccelStepper &stepper, bool &runContinuous) {
  runContinuous = false;
  stepper.setSpeed(0);
  replyOk();
  return true;
}

bool handleSpeedCommand(AccelStepper &stepper, long speed) {
  if (speed <= 0) {
    replyErr();
    return false;
  }
  stepper.setMaxSpeed(speed);
  replyOk();
  return true;
}

bool handleAccelCommand(AccelStepper &stepper, long accel) {
  if (accel <= 0) {
    replyErr();
    return false;
  }
  stepper.setAcceleration(accel);
  replyOk();
  return true;
}

bool handleStepsCommand(AccelStepper &stepper, bool &runContinuous, long steps) {
  runBlockingMove(stepper, runContinuous, steps);
  PiSerial.println("DONE");
  return true;
}

void setup() {
  Serial.begin(115200);   // USB debug
  PiSerial.begin(9600);   // Pi UART

  pinMode(PRIMARY_EN_PIN, OUTPUT);
  digitalWrite(PRIMARY_EN_PIN, LOW);

  primaryStepper.setMaxSpeed(1500);
  primaryStepper.setAcceleration(800);

  gateStepper.setMaxSpeed(1500);
  gateStepper.setAcceleration(800);
}

void loop() {
  if (primaryRunContinuous) {
    primaryStepper.runSpeed();
  }
  if (gateRunContinuous) {
    gateStepper.runSpeed();
  }

  if (PiSerial.available() <= 0) {
    return;
  }

  String msg = PiSerial.readStringUntil('\n');
  msg.trim();

  if (msg == "PING") {
    PiSerial.println("PONG");
    Serial.println("PONG");
    return;
  }

  if (msg.startsWith("ECHO ")) {
    String payload = msg.substring(5);
    PiSerial.println(payload);
    Serial.println(payload);
    return;
  }

  if (msg.startsWith("GATE RUN ")) {
    handleRunCommand(gateStepper, gateRunContinuous, parseValue(msg, 9));
    return;
  }
  if (msg == "GATE STOP") {
    handleStopCommand(gateStepper, gateRunContinuous);
    return;
  }
  if (msg.startsWith("GATE SPEED ")) {
    handleSpeedCommand(gateStepper, parseValue(msg, 11));
    return;
  }
  if (msg.startsWith("GATE ACCEL ")) {
    handleAccelCommand(gateStepper, parseValue(msg, 11));
    return;
  }
  if (msg.startsWith("GATE STEPS ")) {
    handleStepsCommand(gateStepper, gateRunContinuous, parseValue(msg, 11));
    return;
  }

  if (msg.startsWith("RUN ")) {
    handleRunCommand(primaryStepper, primaryRunContinuous, parseValue(msg, 4));
    return;
  }
  if (msg == "STOP") {
    handleStopCommand(primaryStepper, primaryRunContinuous);
    return;
  }
  if (msg.startsWith("SPEED ")) {
    handleSpeedCommand(primaryStepper, parseValue(msg, 6));
    return;
  }
  if (msg.startsWith("ACCEL ")) {
    handleAccelCommand(primaryStepper, parseValue(msg, 6));
    return;
  }
  if (msg.startsWith("SETDIST ")) {
    liftDistance = parseValue(msg, 8);
    replyOk();
    return;
  }
  if (msg.startsWith("STEPS ")) {
    handleStepsCommand(primaryStepper, primaryRunContinuous, parseValue(msg, 6));
    return;
  }
  if (msg == "MOVE") {
    runBlockingMove(primaryStepper, primaryRunContinuous, liftDistance);
    waitingRelease = true;
    PiSerial.println("ARRIVED");
    return;
  }
  if (msg == "RELEASE" && waitingRelease) {
    runBlockingMove(primaryStepper, primaryRunContinuous, -liftDistance);
    waitingRelease = false;
    PiSerial.println("DONE");
    return;
  }

  replyErr();
}
