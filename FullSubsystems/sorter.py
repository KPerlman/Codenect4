import time
import board
import busio
from adafruit_pca9685 import PCA9685
import adafruit_tcs34725
import adafruit_bitbangio as bitbangio
try:
    from adafruit_extended_bus import ExtendedI2C
except ImportError:
    ExtendedI2C = None


SERVO_CHANNEL = 6
MAX_ANGLE = 270
PULSE_MIN = 500
PULSE_MAX = 2500
OFFSET = 0

PLAYER_DROP = 0
RIGHT_PICKUP = 85
LEFT_PICKUP = 165
DETECT = 200
ROBOT_DROP = 270

PICKUP_SETTLE = 0.6
DETECT_SETTLE = 0.4
DROP_SETTLE = 0.8
DROP_HOLD = 1.0

MISS_LIMIT = 3
AGITATE_SWINGS = 4
AGITATE_DELTA = 12

CLEAR_THRESH = 1733.7
RED_MARGIN = 33.0
YELLOW_CLEAR = 1800.0


def move_servo(pca, channel, angle, max_angle=180, offset=0):
    corrected_angle = max(0, min(max_angle, angle + offset))
    pulse = PULSE_MIN + (corrected_angle / float(max_angle)) * (PULSE_MAX - PULSE_MIN)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def classify_color(sensor):
    r, g, b = sensor.color_rgb_bytes
    _, _, _, clear = sensor.color_raw

    if clear < CLEAR_THRESH:
        return "none"
    if clear >= YELLOW_CLEAR:
        return "yellow"
    if r - max(g, b) >= RED_MARGIN:
        return "red"
    return "none"


def agitate(pca, base_angle):
    for _ in range(AGITATE_SWINGS):
        move_servo(pca, SERVO_CHANNEL, base_angle + AGITATE_DELTA, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(0.2)
        move_servo(pca, SERVO_CHANNEL, base_angle - AGITATE_DELTA, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(0.2)
    move_servo(pca, SERVO_CHANNEL, base_angle, max_angle=MAX_ANGLE, offset=OFFSET)


def main():
    i2c_pca = busio.I2C(board.SCL, board.SDA)
    if ExtendedI2C is not None:
        i2c_sorter = ExtendedI2C(3)
    else:
        try:
            i2c_sorter = busio.I2C(board.D17, board.D27)
        except ValueError:
            i2c_sorter = bitbangio.I2C(board.D27, board.D17)

    pca = PCA9685(i2c_pca)
    pca.frequency = 50
    sensor = adafruit_tcs34725.TCS34725(i2c_sorter)
    sensor.integration_time = 100
    sensor.gain = 4

    miss_count = 0
    next_pickup_right = True

    try:
        move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(1.0)

        while True:
            pickup_angle = RIGHT_PICKUP if next_pickup_right else LEFT_PICKUP
            next_pickup_right = not next_pickup_right

            move_servo(pca, SERVO_CHANNEL, pickup_angle, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(PICKUP_SETTLE)

            if miss_count >= MISS_LIMIT:
                agitate(pca, pickup_angle)
                time.sleep(0.2)

            move_servo(pca, SERVO_CHANNEL, DETECT, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(DETECT_SETTLE)

            color = classify_color(sensor)
            if color == "red":
                move_servo(pca, SERVO_CHANNEL, ROBOT_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(DROP_SETTLE)
                time.sleep(DROP_HOLD)
                miss_count = 0
            elif color == "yellow":
                move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(DROP_SETTLE)
                time.sleep(DROP_HOLD)
                miss_count = 0
            else:
                miss_count += 1

    finally:
        move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
        pca.deinit()


if __name__ == "__main__":
    main()
