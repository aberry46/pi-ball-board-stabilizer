#include <Servo.h>
#include <stdlib.h>
#include <string.h>

Servo servoX;
Servo servoY;

// Pins
const int SERVO_X_PIN = 9;
const int SERVO_Y_PIN = 10;

// Editable calibration values
const int SERVO_X_MIN = 12;
const int SERVO_X_NEUTRAL = 27;
const int SERVO_X_MAX = 42;

const int SERVO_Y_MIN = 3;
const int SERVO_Y_NEUTRAL = 18;
const int SERVO_Y_MAX = 33;

// Axis direction
const bool SERVO_X_INVERT = false;
const bool SERVO_Y_INVERT = true;

// Fast reaction tuning
const bool FAST_REACTION_MODE = true;
const bool IMMEDIATE_ON_COMMAND = true;
const int SERVO_STEP_PER_UPDATE = 12;
const unsigned long SERVO_UPDATE_MS = 4;
const unsigned long COMMAND_TIMEOUT_MS = 1000;

// Serial parsing
const unsigned long SERIAL_BAUD = 115200;
const size_t COMMAND_BUFFER_SIZE = 64;

float targetTiltX = 0.0f;
float targetTiltY = 0.0f;

int currentAngleX = SERVO_X_NEUTRAL;
int currentAngleY = SERVO_Y_NEUTRAL;
int targetAngleX = SERVO_X_NEUTRAL;
int targetAngleY = SERVO_Y_NEUTRAL;

unsigned long lastCommandMillis = 0;
unsigned long lastServoUpdateMillis = 0;

char commandBuffer[COMMAND_BUFFER_SIZE];
size_t commandLength = 0;

int clampInt(int value, int minValue, int maxValue) {
  if (value < minValue) return minValue;
  if (value > maxValue) return maxValue;
  return value;
}

float clampFloat(float value, float minValue, float maxValue) {
  if (value < minValue) return minValue;
  if (value > maxValue) return maxValue;
  return value;
}

float applyAxisInvert(float tilt, bool invertAxis) {
  return invertAxis ? -tilt : tilt;
}

int mapTiltToAngle(float tilt, int minAngle, int neutralAngle, int maxAngle) {
  tilt = clampFloat(tilt, -1.0f, 1.0f);

  if (tilt >= 0.0f) {
    return neutralAngle + (int)((maxAngle - neutralAngle) * tilt);
  }

  return neutralAngle + (int)((neutralAngle - minAngle) * tilt);
}

void writeCurrentAngles() {
  servoX.write(currentAngleX);
  servoY.write(currentAngleY);
}

void jumpToTargets() {
  currentAngleX = targetAngleX;
  currentAngleY = targetAngleY;
  writeCurrentAngles();
}

void applyTargetsFromTilt(bool jumpImmediately) {
  targetAngleX = clampInt(
    mapTiltToAngle(applyAxisInvert(targetTiltX, SERVO_X_INVERT), SERVO_X_MIN, SERVO_X_NEUTRAL, SERVO_X_MAX),
    SERVO_X_MIN,
    SERVO_X_MAX
  );

  targetAngleY = clampInt(
    mapTiltToAngle(applyAxisInvert(targetTiltY, SERVO_Y_INVERT), SERVO_Y_MIN, SERVO_Y_NEUTRAL, SERVO_Y_MAX),
    SERVO_Y_MIN,
    SERVO_Y_MAX
  );

  if (jumpImmediately) {
    jumpToTargets();
  }
}

void moveServoTowardTarget(Servo &servo, int &currentAngle, int targetAngle) {
  if (currentAngle == targetAngle) return;

  if (currentAngle < targetAngle) {
    currentAngle += SERVO_STEP_PER_UPDATE;
    if (currentAngle > targetAngle) currentAngle = targetAngle;
  } else {
    currentAngle -= SERVO_STEP_PER_UPDATE;
    if (currentAngle < targetAngle) currentAngle = targetAngle;
  }

  servo.write(currentAngle);
}

void setNeutralTarget(bool jumpImmediately) {
  targetTiltX = 0.0f;
  targetTiltY = 0.0f;
  targetAngleX = SERVO_X_NEUTRAL;
  targetAngleY = SERVO_Y_NEUTRAL;

  if (jumpImmediately) {
    jumpToTargets();
  }
}

void printStatus() {
  Serial.print("STATUS ");
  Serial.print("tilt_x=");
  Serial.print(targetTiltX, 3);
  Serial.print(" tilt_y=");
  Serial.print(targetTiltY, 3);
  Serial.print(" angle_x=");
  Serial.print(currentAngleX);
  Serial.print(" angle_y=");
  Serial.print(currentAngleY);
  Serial.print(" target_x=");
  Serial.print(targetAngleX);
  Serial.print(" target_y=");
  Serial.println(targetAngleY);
}

void printHelp() {
  Serial.println("Commands:");
  Serial.println("  TILT <x> <y>   normalized tilt command in range [-1.0, 1.0]");
  Serial.println("  CENTER         return both servos to neutral");
  Serial.println("  STATUS         print current targets and angles");
  Serial.println("  HELP           print this message");
  Serial.println();
  Serial.println("Fast reaction mode is enabled.");
}

bool parseTiltValues(const char *command, float &x, float &y) {
  char buffer[COMMAND_BUFFER_SIZE];
  strncpy(buffer, command, COMMAND_BUFFER_SIZE - 1);
  buffer[COMMAND_BUFFER_SIZE - 1] = '\0';

  char *token = strtok(buffer, " ");
  if (token == NULL || strcmp(token, "TILT") != 0) {
    return false;
  }

  char *xToken = strtok(NULL, " ");
  char *yToken = strtok(NULL, " ");
  char *extraToken = strtok(NULL, " ");

  if (xToken == NULL || yToken == NULL || extraToken != NULL) {
    return false;
  }

  char *xEnd = NULL;
  char *yEnd = NULL;
  x = strtof(xToken, &xEnd);
  y = strtof(yToken, &yEnd);

  if (xEnd == xToken || yEnd == yToken) {
    return false;
  }

  while (*xEnd == ' ') xEnd++;
  while (*yEnd == ' ') yEnd++;

  if (*xEnd != '\0' || *yEnd != '\0') {
    return false;
  }

  return true;
}

void handleTiltCommand(const char *command) {
  float x = 0.0f;
  float y = 0.0f;

  if (!parseTiltValues(command, x, y)) {
    Serial.println("ERR invalid TILT format");
    return;
  }

  targetTiltX = clampFloat(x, -1.0f, 1.0f);
  targetTiltY = clampFloat(y, -1.0f, 1.0f);
  applyTargetsFromTilt(FAST_REACTION_MODE && IMMEDIATE_ON_COMMAND);
  lastCommandMillis = millis();

  Serial.print("OK TILT ");
  Serial.print(targetTiltX, 3);
  Serial.print(" ");
  Serial.println(targetTiltY, 3);
}

void handleCommand(const char *command) {
  if (strncmp(command, "TILT ", 5) == 0) {
    handleTiltCommand(command);
    return;
  }

  if (strcmp(command, "CENTER") == 0) {
    setNeutralTarget(FAST_REACTION_MODE && IMMEDIATE_ON_COMMAND);
    lastCommandMillis = millis();
    Serial.println("OK CENTER");
    return;
  }

  if (strcmp(command, "STATUS") == 0) {
    printStatus();
    return;
  }

  if (strcmp(command, "HELP") == 0) {
    printHelp();
    return;
  }

  Serial.println("ERR unknown command");
}

void pollSerialCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      commandBuffer[commandLength] = '\0';
      if (commandLength > 0) {
        handleCommand(commandBuffer);
      }
      commandLength = 0;
      continue;
    }

    if (commandLength < (COMMAND_BUFFER_SIZE - 1)) {
      commandBuffer[commandLength++] = c;
    } else {
      commandLength = 0;
      Serial.println("ERR command too long");
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);

  servoX.attach(SERVO_X_PIN);
  servoY.attach(SERVO_Y_PIN);

  writeCurrentAngles();
  setNeutralTarget(true);
  lastCommandMillis = millis();
  lastServoUpdateMillis = millis();

  Serial.println("Pi ball-board servo controller ready");
  printStatus();
  printHelp();
}

void loop() {
  pollSerialCommands();

  if (millis() - lastCommandMillis > COMMAND_TIMEOUT_MS) {
    setNeutralTarget(FAST_REACTION_MODE && IMMEDIATE_ON_COMMAND);
  }

  if (!IMMEDIATE_ON_COMMAND && millis() - lastServoUpdateMillis >= SERVO_UPDATE_MS) {
    lastServoUpdateMillis = millis();
    moveServoTowardTarget(servoX, currentAngleX, targetAngleX);
    moveServoTowardTarget(servoY, currentAngleY, targetAngleY);
  }
}
