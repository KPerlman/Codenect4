import time
import board
import busio
from adafruit_pca9685 import PCA9685


def move_servo(pca, channel, angle, max_angle=180):
    pulse_min = 450
    pulse_max = 2550
    corrected_angle = max(0, min(max_angle, angle))
    pulse = pulse_min + (corrected_angle / float(max_angle)) * (pulse_max - pulse_min)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def main():
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c)
    pca.frequency = 50

    print("Sweeping servos 0-6. Ctrl+C to stop.")
    try:
        while True:
            for channel in range(7):
                if channel == 6:
                    print("Servo 6 -> 270")
                    move_servo(pca, channel, 270, max_angle=270)
                    time.sleep(1)
                    print("Servo 6 -> 0")
                    move_servo(pca, channel, 0, max_angle=270)
                    time.sleep(1)
                else:
                    print(f"Servo {channel} -> 90")
                    move_servo(pca, channel, 90)
                    time.sleep(1)
                    print(f"Servo {channel} -> 0")
                    move_servo(pca, channel, 0)
                    time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for channel in range(7):
            move_servo(pca, channel, 0)
        pca.deinit()


if __name__ == "__main__":
    main()
