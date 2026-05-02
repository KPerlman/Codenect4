import time
import sys
from pathlib import Path
import board
import busio
import serial
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tcs_bus import open_tcs34725


PORT = "/dev/serial0"
DEFAULT_SPEED = 1000
BOOST_SPEED = 4000
BOOST_STEPS = 250
ACCEL = 400
CLEAR_THRESH = 1733.7
SAMPLE_DELAY = 0.05


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


def boost(ser):
    send_cmd(ser, "STOP", {"OK"})
    send_cmd(ser, f"SPEED {BOOST_SPEED}", {"OK", "ERR"})
    send_cmd(ser, f"STEPS {BOOST_STEPS}", {"DONE"})
    send_cmd(ser, f"SPEED {DEFAULT_SPEED}", {"OK", "ERR"})
    send_cmd(ser, f"RUN {DEFAULT_SPEED}", {"OK", "ERR"})


def main():
    sensor = open_tcs34725(3, integration_time_ms=100, gain=4)

    ser = serial.Serial(PORT, 9600, timeout=1)
    time.sleep(2)
    ser.reset_input_buffer()

    send_cmd(ser, f"SPEED {DEFAULT_SPEED}", {"OK", "ERR"})
    send_cmd(ser, f"ACCEL {ACCEL}", {"OK", "ERR"})
    send_cmd(ser, f"RUN {DEFAULT_SPEED}", {"OK", "ERR"})

    last_present = False

    print("Belt loop running. Ctrl+C to stop.")
    try:
        while True:
            _, _, _, clear = sensor.color_raw
            present = clear >= CLEAR_THRESH

            if present and not last_present:
                print("Piece detected -> boost")
                boost(ser)
                last_present = False
            else:
                last_present = present

            time.sleep(SAMPLE_DELAY)
    except KeyboardInterrupt:
        send_cmd(ser, "STOP", {"OK"})
    finally:
        ser.close()


if __name__ == "__main__":
    main()
