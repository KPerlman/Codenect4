import argparse
import time
import serial


def wait_for(arduino, targets, timeout_s=5.0):
    deadline = time.time() + timeout_s
    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timeout waiting for {targets}")
        line = arduino.readline().decode(errors="ignore").strip()
        if line:
            print("<", line)
        if line in targets:
            return line


def main():
    parser = argparse.ArgumentParser(
        description="Stepper test (one direction). Default: run continuously until Ctrl+C."
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=600,
        help="Max speed in steps/sec (default: 600)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=None,
        help="If set, move this many steps once then exit",
    )
    args = parser.parse_args()

    port = "/dev/serial0"
    arduino = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)
    arduino.reset_input_buffer()

    speed_cmd = f"SPEED {args.speed}\n".encode()
    print(f"Setting SPEED {args.speed}")
    arduino.write(speed_cmd)
    wait_for(arduino, {"OK", "ERR"})

    print("Setting ACCEL 400")
    arduino.write(b"ACCEL 400\n")
    wait_for(arduino, {"OK", "ERR"})

    if args.steps is not None:
        print(f"Setting SETDIST {args.steps}")
        arduino.write(f"SETDIST {args.steps}\n".encode())
        wait_for(arduino, {"OK", "ERR"})

        print(f"Sending STEPS {args.steps}")
        arduino.write(f"STEPS {args.steps}\n".encode())
        wait_for(arduino, {"DONE"})
    else:
        print("Running continuously (Ctrl+C to stop)")
        try:
            while True:
                arduino.write(b"STEPS 1000\n")
                wait_for(arduino, {"DONE"})
        except KeyboardInterrupt:
            pass

    arduino.close()


if __name__ == "__main__":
    main()
