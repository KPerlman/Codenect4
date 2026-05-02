import argparse
import time
import sys
from pathlib import Path
import board
import serial
import adafruit_tcs34725
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import adafruit_bitbangio as linux_bitbangio
except ImportError:
    linux_bitbangio = None

import bitbangio

PORT = "/dev/serial0"
DEFAULT_SPEED = 1000
BOOST_SPEED = 5000
BOOST_STEPS = 3000
CALIBRATE_STEPS = 750
ACCEL = 2000
CLEAR_THRESH = 2051.0
SAMPLE_DELAY = 0.05
CONFIRM_READS = 3


def open_belt_tcs34725(integration_time_ms=100, gain=4):
    # Belt TCS34725 is wired to a software I2C pair on GPIO23/24.
    bitbang_mod = linux_bitbangio or bitbangio
    try:
        i2c = bitbang_mod.I2C(board.D23, board.D24)
    except NotImplementedError as exc:
        raise RuntimeError(
            "Software I2C on GPIO23/24 requires the Linux package "
            "'Adafruit-CircuitPython-BitbangIO'. Install it in your venv and try again."
        ) from exc
    sensor = adafruit_tcs34725.TCS34725(i2c)
    sensor.integration_time = integration_time_ms
    sensor.gain = gain
    return sensor


def wait_for(ser, targets, timeout_s=2.0):
    deadline = time.time() + timeout_s
    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timeout waiting for {targets}")
        line = ser.readline().decode(errors="ignore").strip()
        line = "".join(ch for ch in line if ch.isprintable())
        if line:
            print("<", line)
        if line in targets:
            return line


def send_cmd(ser, cmd, expect=None, timeout_s=2.0, attempts=3, pre_delay_s=0.1):
    if expect is None:
        ser.write(f"{cmd}\n".encode())
        return None

    last_error = None
    for attempt in range(1, attempts + 1):
        time.sleep(pre_delay_s)
        ser.write(f"{cmd}\n".encode())
        try:
            return wait_for(ser, expect, timeout_s=timeout_s)
        except TimeoutError as exc:
            last_error = exc
            if attempt < attempts:
                print(f"No response to {cmd!r}, retrying ({attempt}/{attempts})...")
                ser.reset_input_buffer()
                time.sleep(0.2)
    raise last_error


def sync_controller(ser, attempts=6, timeout_s=1.5):
    for attempt in range(1, attempts + 1):
        print(f"Pinging controller ({attempt}/{attempts})")
        ser.write(b"PING\n")
        try:
            wait_for(ser, {"PONG"}, timeout_s=timeout_s)
            time.sleep(0.3)
            ser.reset_input_buffer()
            return
        except TimeoutError:
            ser.reset_input_buffer()
            time.sleep(0.3)
    raise TimeoutError("Controller did not respond to PING")


def read_clear(sensor, reads=CONFIRM_READS):
    samples = []
    for _ in range(reads):
        _, _, _, clear = sensor.color_raw
        samples.append(clear)
        time.sleep(SAMPLE_DELAY)
    return sum(samples) / len(samples)


def summarize(samples):
    if not samples:
        return None
    return {
        "count": len(samples),
        "min": min(samples),
        "max": max(samples),
        "avg": sum(samples) / len(samples),
    }


def update_threshold(piece_samples, empty_samples, current_thresh):
    if piece_samples and empty_samples:
        return (max(empty_samples) + min(piece_samples)) / 2.0
    if piece_samples:
        return min(piece_samples) - 1.0
    if empty_samples:
        return max(empty_samples) + 1.0
    return current_thresh


def print_run_command(clear_thresh):
    print("\nRun with:")
    print(
        "python3 FullSubsystems/belt.py "
        f"--clear-thresh {clear_thresh:.1f}"
    )


def boost(ser):
    send_cmd(ser, "STOP", {"OK"})
    send_cmd(ser, f"SPEED {BOOST_SPEED}", {"OK", "ERR"})
    send_cmd(ser, f"STEPS {BOOST_STEPS}", {"DONE"}, timeout_s=10.0)
    send_cmd(ser, f"SPEED {DEFAULT_SPEED}", {"OK", "ERR"})
    send_cmd(ser, f"RUN {DEFAULT_SPEED}", {"OK", "ERR"})


def sample_present(sensor, threshold):
    clear = read_clear(sensor)
    return clear >= threshold, clear


def calibrate_mode(ser, sensor, initial_clear_thresh):
    clear_thresh = initial_clear_thresh
    piece_samples = []
    empty_samples = []

    print("Belt calibration mode")
    print("Moves 250 steps between entries. Labels: p=piece, e=empty, q=quit")

    try:
        while True:
            send_cmd(ser, f"STEPS {CALIBRATE_STEPS}", {"DONE"}, timeout_s=10.0)
            clear = read_clear(sensor)
            guess = "piece" if clear >= clear_thresh else "empty"
            print(f"Clear={clear:.1f} guess={guess} threshold={clear_thresh:.1f}")

            label = input("Label [p/e/q]: ").strip().lower()
            if label == "q":
                break
            if label not in {"p", "e"}:
                print("Use p, e, or q.")
                continue

            if label == "p":
                piece_samples.append(clear)
            else:
                empty_samples.append(clear)

            new_thresh = update_threshold(piece_samples, empty_samples, clear_thresh)
            if new_thresh != clear_thresh:
                clear_thresh = new_thresh
                print(f"Updated clear threshold -> {clear_thresh:.1f}")

    finally:
        print("\n--- Calibration Summary ---")
        piece_stats = summarize(piece_samples)
        empty_stats = summarize(empty_samples)
        if piece_stats:
            print(
                f"piece: count={piece_stats['count']} avg={piece_stats['avg']:.1f} "
                f"range=({piece_stats['min']:.1f}-{piece_stats['max']:.1f})"
            )
        else:
            print("piece: no samples")
        if empty_stats:
            print(
                f"empty: count={empty_stats['count']} avg={empty_stats['avg']:.1f} "
                f"range=({empty_stats['min']:.1f}-{empty_stats['max']:.1f})"
            )
        else:
            print("empty: no samples")

        if piece_samples and empty_samples:
            final_thresh = update_threshold(piece_samples, empty_samples, clear_thresh)
            print(f"Suggested clear threshold: {final_thresh:.1f}")
            print_run_command(final_thresh)
        else:
            print(f"Suggested clear threshold: {clear_thresh:.1f}")
            print_run_command(clear_thresh)


def main():
    parser = argparse.ArgumentParser(description="Belt control / calibration")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run calibration mode: move 250 steps between samples and print thresholds",
    )
    parser.add_argument(
        "--clear-thresh",
        type=float,
        default=CLEAR_THRESH,
        help="Clear threshold used to detect a belt piece",
    )
    args = parser.parse_args()

    sensor = open_belt_tcs34725(integration_time_ms=100, gain=4)

    ser = serial.Serial(PORT, 9600, timeout=1)
    try:
        time.sleep(2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        sync_controller(ser)

        send_cmd(ser, f"SPEED {DEFAULT_SPEED}", {"OK", "ERR"})
        send_cmd(ser, f"ACCEL {ACCEL}", {"OK", "ERR"})

        if args.calibrate:
            calibrate_mode(ser, sensor, args.clear_thresh)
            send_cmd(ser, "STOP", {"OK"})
            return

        send_cmd(ser, f"RUN {DEFAULT_SPEED}", {"OK", "ERR"})

        clear_thresh = args.clear_thresh
        piece_samples = []
        empty_samples = []
        last_present = False

        print("Belt loop running. Ctrl+C to stop.")
        while True:
            present, clear = sample_present(sensor, clear_thresh)

            if present and not last_present:
                print(f"Piece detected (clear={clear:.1f}). Pausing belt for confirmation.")
                send_cmd(ser, "STOP", {"OK"})
                confirmation = input("Launch piece? [y/n]: ").strip().lower()
                if confirmation in {"y", "yes"}:
                    print("Launching piece.")
                    piece_samples.append(clear)
                    new_thresh = update_threshold(piece_samples, empty_samples, clear_thresh)
                    if new_thresh != clear_thresh:
                        clear_thresh = new_thresh
                        print(f"Updated clear threshold -> {clear_thresh:.1f}")
                    boost(ser)
                else:
                    empty_samples.append(clear)
                    new_thresh = update_threshold(piece_samples, empty_samples, clear_thresh)
                    if new_thresh != clear_thresh:
                        clear_thresh = new_thresh
                        print(f"Updated clear threshold -> {clear_thresh:.1f}")
                    print(f"Resuming belt at {DEFAULT_SPEED} steps/sec.")
                    send_cmd(ser, f"SPEED {DEFAULT_SPEED}", {"OK", "ERR"})
                    send_cmd(ser, f"RUN {DEFAULT_SPEED}", {"OK", "ERR"})
                last_present = False
            else:
                last_present = present

            time.sleep(SAMPLE_DELAY)
    except KeyboardInterrupt:
        try:
            send_cmd(ser, "STOP", {"OK"})
        except TimeoutError:
            print("STOP sent but no OK received before timeout.")
    finally:
        if 'piece_samples' in locals() and (piece_samples or empty_samples):
            print("\n--- Calibration Summary ---")
            piece_stats = summarize(piece_samples)
            empty_stats = summarize(empty_samples)
            if piece_stats:
                print(
                    f"piece: count={piece_stats['count']} avg={piece_stats['avg']:.1f} "
                    f"range=({piece_stats['min']:.1f}-{piece_stats['max']:.1f})"
                )
            else:
                print("piece: no samples")
            if empty_stats:
                print(
                    f"empty: count={empty_stats['count']} avg={empty_stats['avg']:.1f} "
                    f"range=({empty_stats['min']:.1f}-{empty_stats['max']:.1f})"
                )
            else:
                print("empty: no samples")

            if piece_samples and empty_samples:
                final_thresh = update_threshold(piece_samples, empty_samples, clear_thresh)
                print(f"Suggested clear threshold: {final_thresh:.1f}")
                print_run_command(final_thresh)
            else:
                print(f"Suggested clear threshold: {clear_thresh:.1f}")
                print_run_command(clear_thresh)
        ser.close()


if __name__ == "__main__":
    main()
