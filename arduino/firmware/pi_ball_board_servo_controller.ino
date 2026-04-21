#include <Servo.h>

Servo servoX;
Servo servoY;

const int SERVO_X_PIN = 9;
const int SERVO_Y_PIN = 10;

const int SERVO_X_MIN = 17;
const int SERVO_X_NEUTRAL = 27;
const int SERVO_X_MAX = 37;

const int SERVO_Y_MIN = 8;
const int SERVO_Y_NEUTRAL = 18;
const int SERVO_Y_MAX = 28;

const bool SERVO_X_INVERT = false;
const bool SERVO_Y_INVERT = true;

const unsigned long SERIAL_BAUD = 115200;
const unsigned long COMMAND_TIMEOUT_MS = 250;
const size_t COMMAND_BUFFER_SIZE = 48;

float targetTiltX = 0.0f;
float targetTiltY = 0.0f;
int currentAngleX = SERVO_X_NEUTRAL;
int currentAngleY = SERVO_Y_NEUTRAL;
unsigned long lastCommandMillis = 0;
char commandBuffer[COMMAND_BUFFER_SIZE];
size_t commandLength = 0;

int clampInt(int value, int lo, int hi) {
  if (value < lo) return lo;
  if (value > hi) return hi;
  return value;
}

float clampFloat(float value, float lo, float hi) {
  if (value < lo) return lo;
  if (value > hi) return hi;
  return value;
}

float applyInvert(float value, bool invert) {
  return invert ? -value : value;
}

int mapTiltToAngle(float tilt, int minAngle, int neutralAngle, int maxAngle) {
  tilt = clampFloat(tilt, -1.0f, 1.0f);
  if (tilt >= 0.0f) {
    return neutralAngle + (int)((maxAngle - neutralAngle) * tilt);
  }
  return neutralAngle + (int)((neutralAngle - minAngle) * tilt);
}

void applyTargets() {
  currentAngleX = clampInt(
    mapTiltToAngle(applyInvert(targetTiltX, SERVO_X_INVERT), SERVO_X_MIN, SERVO_X_NEUTRAL, SERVO_X_MAX),
    SERVO_X_MIN,
    SERVO_X_MAX
  );
  currentAngleY = clampInt(
    mapTiltToAngle(applyInvert(targetTiltY, SERVO_Y_INVERT), SERVO_Y_MIN, SERVO_Y_NEUTRAL, SERVO_Y_MAX),
    SERVO_Y_MIN,
    SERVO_Y_MAX
  );
  servoX.write(currentAngleX);
  servoY.write(currentAngleY);
}

void setNeutral() {
  targetTiltX = 0.0f;
  targetTiltY = 0.0f;
  currentAngleX = SERVO_X_NEUTRAL;
  currentAngleY = SERVO_Y_NEUTRAL;
  servoX.write(currentAngleX);
  servoY.write(currentAngleY);
}

void printStatus() {
  Serial.print("STATUS angle_x=");
  Serial.print(currentAngleX);
  Serial.print(" angle_y=");
  Serial.print(currentAngleY);
  Serial.print(" tilt_x=");
  Serial.print(targetTiltX, 3);
  Serial.print(" tilt_y=");
  Serial.println(targetTiltY, 3);
}

void handleTilt(const char *command) {
  float x = 0.0f;
  float y = 0.0f;
  if (sscanf(command, "TILT %f %f", &x, &y) != 2) {
    Serial.println("ERR invalid TILT format");
    return;
  }
  targetTiltX = clampFloat(x, -1.0f, 1.0f);
  targetTiltY = clampFloat(y, -1.0f, 1.0f);
  applyTargets();
  lastCommandMillis = millis();
  Serial.println("OK TILT");
}

void handleCommand(const char *command) {
  if (strncmp(command, "TILT ", 5) == 0) {
    handleTilt(command);
    return;
  }
  if (strcmp(command, "CENTER") == 0) {
    setNeutral();
    lastCommandMillis = millis();
    Serial.println("OK CENTER");
    return;
  }
  if (strcmp(command, "STATUS") == 0) {
    printStatus();
    return;
  }
  if (strcmp(command, "HELP") == 0) {
    Serial.println("Commands: TILT <x> <y>, CENTER, STATUS, HELP");
    return;
  }
  Serial.println("ERR unknown command");
}

void pollSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      commandBuffer[commandLength] = '\0';
      if (commandLength > 0) {
        handleCommand(commandBuffer);
      }
      commandLength = 0;
      continue;
    }
    if (commandLength < COMMAND_BUFFER_SIZE - 1) {
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
  setNeutral();
  lastCommandMillis = millis();
  Serial.println("Pi ball-board servo controller ready");
}

void loop() {
  pollSerial();
  if (millis() - lastCommandMillis > COMMAND_TIMEOUT_MS) {
    setNeutral();
  }
}
