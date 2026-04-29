import time
import board
import busio
from adafruit_pca9685 import PCA9685
import adafruit_tcs34725


def move_servo(pca, channel, angle):
    pulse_min = 450
    pulse_max = 2550
    corrected_angle = max(0, min(180, angle))
    pulse = pulse_min + (corrected_angle / 180.0) * (pulse_max - pulse_min)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def main():
    i2c_pca = busio.I2C(board.SCL, board.SDA)
    i2c_top = busio.I2C(board.D17, board.D27)
    i2c_bottom = busio.I2C(board.D23, board.D24)

    pca = PCA9685(i2c_pca)
    pca.frequency = 50

    top_sensor = adafruit_tcs34725.TCS34725(i2c_top)
    bottom_sensor = adafruit_tcs34725.TCS34725(i2c_bottom)

    top_sensor.integration_time = 100
    top_sensor.gain = 4
    bottom_sensor.integration_time = 100
    bottom_sensor.gain = 4

    angles = [0, 90]
    idx = 0

    print("Starting servo + color sensor test. Ctrl+C to stop.")
    try:
        while True:
            angle = angles[idx % 2]
            for channel in range(3):
                move_servo(pca, channel, angle)

            top_clear = top_sensor.clear
            bottom_clear = bottom_sensor.clear
            top_rgb = top_sensor.color_rgb_bytes
            bottom_rgb = bottom_sensor.color_rgb_bytes

            print(
                f"angle={angle} top_clear={top_clear} top_rgb={top_rgb} "
                f"bottom_clear={bottom_clear} bottom_rgb={bottom_rgb}"
            )

            idx += 1
            time.sleep(1.0)
    finally:
        for channel in range(3):
            move_servo(pca, channel, 0)
        pca.deinit()


if __name__ == "__main__":
    main()
