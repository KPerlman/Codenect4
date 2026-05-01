import argparse
import time
import board
import busio
from adafruit_pca9685 import PCA9685


def move_servo(pca, channel, angle, pulse_min=450, pulse_max=2550):
    corrected_angle = max(0, min(180, angle))
    pulse = pulse_min + (corrected_angle / 180.0) * (pulse_max - pulse_min)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def prompt_offset_or_accept(current):
    prompt = f"Enter offset degrees (current {current}) or 'y' to accept: "
    while True:
        val = input(prompt).strip().lower()
        if val in {"y", "yes"}:
            return True, current
        try:
            return False, int(val)
        except ValueError:
            print("Type 'y' to accept or enter an integer (negative allowed).")


def main():
    parser = argparse.ArgumentParser(
        description="Servo zero calibration for PCA9685 channels."
    )
    parser.add_argument(
        "start",
        type=int,
        nargs="?",
        default=0,
        help="Starting servo channel (default: 0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=6,
        help="Number of servos to calibrate (default: 6)",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=0.6,
        help="Seconds to wait after each move (default: 0.6)",
    )
    args = parser.parse_args()

    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c)
    pca.frequency = 50

    offsets = [0] * 7

    try:
        end = min(args.start + args.count, 7)
        for channel in range(args.start, end):
            offset = 0
            while True:
                print(f"Servo {channel} -> offset {offset} degrees")
                move_servo(pca, channel, offset)
                time.sleep(args.settle)

                accepted, new_offset = prompt_offset_or_accept(offset)
                if accepted:
                    break

                offset = new_offset
                move_servo(pca, channel, 90)
                time.sleep(args.settle)
                move_servo(pca, channel, offset)
                time.sleep(args.settle)

            offsets[channel] = offset
            print(f"Locked servo {channel} offset: {offset}\n")

        print("Calibration complete.")
        print("Offsets list (channels 0-6):")
        print(offsets)
    finally:
        for channel in range(7):
            move_servo(pca, channel, 0)
        pca.deinit()


if __name__ == "__main__":
    main()
