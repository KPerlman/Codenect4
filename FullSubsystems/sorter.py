import time
import board
import busio
from adafruit_pca9685 import PCA9685


SERVO_CHANNEL = 6
MAX_ANGLE = 270
STEP_DEG = 10
START_WAIT = 3.0
STEP_WAIT = 1.0
END_WAIT = 5.0
OFFSET = 0


def move_servo(pca, channel, angle, max_angle=180, offset=0):
    pulse_min = 450
    pulse_max = 2550
    corrected_angle = max(0, min(max_angle, angle + offset))
    pulse = pulse_min + (corrected_angle / float(max_angle)) * (pulse_max - pulse_min)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def main():
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c)
    pca.frequency = 50

    try:
        print(f"Servo {SERVO_CHANNEL} -> 0")
        move_servo(pca, SERVO_CHANNEL, 0, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(START_WAIT)

        for angle in range(STEP_DEG, MAX_ANGLE + 1, STEP_DEG):
            print(f"Servo {SERVO_CHANNEL} -> {angle}")
            move_servo(pca, SERVO_CHANNEL, angle, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(STEP_WAIT)

        print(f"Servo {SERVO_CHANNEL} -> {MAX_ANGLE} (hold)")
        time.sleep(END_WAIT)

        print(f"Servo {SERVO_CHANNEL} -> 0")
        move_servo(pca, SERVO_CHANNEL, 0, max_angle=MAX_ANGLE, offset=OFFSET)
    finally:
        pca.deinit()


if __name__ == "__main__":
    main()
