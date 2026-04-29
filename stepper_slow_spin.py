import time
import serial


def wait_for(arduino, target, timeout_s=10.0):
    deadline = time.time() + timeout_s
    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timeout waiting for {target}")
        line = arduino.readline().decode(errors="ignore").strip()
        if line:
            print("<", line)
        if line == target:
            return


def main():
    port = "/dev/ttyACM0"
    arduino = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)
    arduino.reset_input_buffer()

    print("> SPEED 400")
    arduino.write(b"SPEED 400\n")
    wait_for(arduino, "OK")

    print("> ACCEL 300")
    arduino.write(b"ACCEL 300\n")
    wait_for(arduino, "OK")

    print("> SETDIST 600")
    arduino.write(b"SETDIST 600\n")
    wait_for(arduino, "OK")

    print("Cycling MOVE/RELEASE. Ctrl+C to stop.")
    try:
        while True:
            print("> MOVE")
            arduino.write(b"MOVE 0\n")
            wait_for(arduino, "ARRIVED")
            time.sleep(0.5)

            print("> RELEASE")
            arduino.write(b"RELEASE\n")
            wait_for(arduino, "DONE")
            time.sleep(1.0)
    finally:
        arduino.close()


if __name__ == "__main__":
    main()
