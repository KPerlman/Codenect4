import time
import sys
from pathlib import Path
import serial
import board
import adafruit_tcs34725

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import adafruit_bitbangio as linux_bitbangio
except ImportError:
    linux_bitbangio = None

import bitbangio

PORT = "/dev/serial0"
DEFAULT_SPEED = 4000
STEP_SIZE = 1500
ACCEL = 400


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
            return None
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print("<", line)
        if line in targets:
            return line


def send_cmd(ser, cmd, expect=None):
    ser.write(f"{cmd}\n".encode())
    if expect:
        return wait_for(ser, expect)
    return None


def read_sample(sensor, count=5, delay_s=0.05):
    r_total = g_total = b_total = c_total = 0
    for _ in range(count):
        r, g, b = sensor.color_rgb_bytes
        _, _, _, clear = sensor.color_raw
        r_total += r
        g_total += g
        b_total += b
        c_total += clear
        time.sleep(delay_s)
    return (
        r_total / count,
        g_total / count,
        b_total / count,
        c_total / count,
    )


def summarize(samples):
    if not samples:
        return None
    cs = [s[3] for s in samples]
    return {
        "count": len(samples),
        "c_avg": sum(cs) / len(cs),
        "c_min": min(cs),
        "c_max": max(cs),
    }


def main():
    sensor = open_belt_tcs34725(integration_time_ms=100, gain=4)

    ser = serial.Serial(PORT, 9600, timeout=1)
    time.sleep(2)
    ser.reset_input_buffer()

    send_cmd(ser, f"SPEED {DEFAULT_SPEED}", {"OK", "ERR"})
    send_cmd(ser, f"ACCEL {ACCEL}", {"OK", "ERR"})

    piece_samples = []
    empty_samples = []

    print("Belt TCS calibration")
    print("Labels: p=piece, e=empty, q=quit")

    try:
        while True:
            label = input("Label [p/e/q]: ").strip().lower()
            if label == "q":
                break
            if label not in {"p", "e"}:
                print("Use p, e, or q.")
                continue

            r, g, b, clear = read_sample(sensor)
            print(f"Sample r={r:.1f} g={g:.1f} b={b:.1f} clear={clear:.1f}")

            if label == "p":
                piece_samples.append((r, g, b, clear))
            else:
                empty_samples.append((r, g, b, clear))

            send_cmd(ser, f"STEPS {STEP_SIZE}", {"DONE"})
            time.sleep(0.2)
    finally:
        ser.close()

    piece_stats = summarize(piece_samples)
    empty_stats = summarize(empty_samples)

    print("\n--- Summary ---")
    if piece_stats:
        print(
            f"piece: count={piece_stats['count']} "
            f"clear_avg={piece_stats['c_avg']:.1f} "
            f"clear_range=({piece_stats['c_min']:.1f}-{piece_stats['c_max']:.1f})"
        )
    else:
        print("piece: no samples")

    if empty_stats:
        print(
            f"empty: count={empty_stats['count']} "
            f"clear_avg={empty_stats['c_avg']:.1f} "
            f"clear_range=({empty_stats['c_min']:.1f}-{empty_stats['c_max']:.1f})"
        )
    else:
        print("empty: no samples")

    if piece_stats and empty_stats:
        clear_thresh = (piece_stats["c_min"] + empty_stats["c_max"]) / 2.0
        print(f"Suggested clear threshold: {clear_thresh:.1f}")


if __name__ == "__main__":
    main()
