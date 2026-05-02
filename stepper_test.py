import argparse
import time
import serial


def wait_for(arduino, targets, timeout_s=5.0):
    deadline = time.time() + timeout_s
    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timeout waiting for {targets}")
        line = arduino.readline().decode(errors="ignore").strip()
        line = "".join(ch for ch in line if ch.isprintable())
        if line:
            print("<", line)
        if line in targets:
            return line


def send_and_wait(arduino, command, targets, timeout_s=5.0, attempts=3, pre_delay_s=0.1):
    last_error = None
    for attempt in range(1, attempts + 1):
        time.sleep(pre_delay_s)
        arduino.write(f"{command}\n".encode())
        try:
            return wait_for(arduino, targets, timeout_s=timeout_s)
        except TimeoutError as exc:
            last_error = exc
            if attempt < attempts:
                print(f"No response to {command!r}, retrying ({attempt}/{attempts})...")
                arduino.reset_input_buffer()
                time.sleep(0.2)
    raise last_error


def sync_controller(arduino, attempts=6, timeout_s=1.5):
    for attempt in range(1, attempts + 1):
        print(f"Pinging controller ({attempt}/{attempts})")
        arduino.write(b"PING\n")
        try:
            wait_for(arduino, {"PONG"}, timeout_s=timeout_s)
            time.sleep(0.3)
            arduino.reset_input_buffer()
            return
        except TimeoutError:
            arduino.reset_input_buffer()
            time.sleep(0.3)
    raise TimeoutError("Controller did not respond to PING")


def run_interactive(arduino, speed):
    running = False

    def start_motor():
        nonlocal running
        print(f"Starting motor at {speed} steps/sec")
        send_and_wait(arduino, f"RUN {speed}", {"OK", "ERR"})
        running = True

    def stop_motor():
        nonlocal running
        print("Stopping motor")
        send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0)
        running = False

    start_motor()
    print("Controls: [Enter]/r=start, s=stop, q=quit")

    while True:
        try:
            command = input("> ").strip().lower()
        except EOFError:
            command = "q"

        if command in {"", "r", "run", "start"}:
            if running:
                print("Motor is already running")
            else:
                start_motor()
        elif command in {"s", "stop"}:
            if running:
                stop_motor()
            else:
                print("Motor is already stopped")
        elif command in {"q", "quit", "exit"}:
            if running:
                stop_motor()
            break
        else:
            print("Use r/start, s/stop, or q/quit")


def main():
    parser = argparse.ArgumentParser(
        description="Stepper test (one direction). Default: run continuously until Ctrl+C."
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=600,
        help="RUN speed in steps/sec (default: 600)",
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
    try:
        time.sleep(2)
        arduino.reset_input_buffer()
        arduino.reset_output_buffer()

        sync_controller(arduino)

        print(f"Setting SPEED {args.speed}")
        send_and_wait(arduino, f"SPEED {args.speed}", {"OK", "ERR"})

        print("Setting ACCEL 400")
        send_and_wait(arduino, "ACCEL 400", {"OK", "ERR"})

        if args.steps is not None:
            print(f"Setting SETDIST {args.steps}")
            send_and_wait(arduino, f"SETDIST {args.steps}", {"OK", "ERR"})

            print(f"Sending STEPS {args.steps}")
            send_and_wait(arduino, f"STEPS {args.steps}", {"DONE"}, timeout_s=10.0)
        else:
            print(f"Interactive mode at {args.speed} steps/sec")
            try:
                run_interactive(arduino, args.speed)
            except KeyboardInterrupt:
                print("\nStopping stepper...")
                try:
                    send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0)
                except KeyboardInterrupt:
                    print("\nStop wait interrupted; exiting without confirmation.")
                except TimeoutError:
                    print("STOP sent but no OK received before timeout.")
    finally:
        arduino.close()


if __name__ == "__main__":
    main()
