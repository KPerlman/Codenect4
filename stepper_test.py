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
    port = "/dev/ttyACM0"
    arduino = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)
    arduino.reset_input_buffer()

    print("Setting SPEED 600")
    arduino.write(b"SPEED 600\n")
    wait_for(arduino, {"OK", "ERR"})

    print("Setting ACCEL 400")
    arduino.write(b"ACCEL 400\n")
    wait_for(arduino, {"OK", "ERR"})

    print("Setting SETDIST 800")
    arduino.write(b"SETDIST 800\n")
    wait_for(arduino, {"OK", "ERR"})

    print("Sending STEPS 200")
    arduino.write(b"STEPS 200\n")
    wait_for(arduino, {"DONE"})

    print("Sending STEPS -200")
    arduino.write(b"STEPS -200\n")
    wait_for(arduino, {"DONE"})

    print("Sending MOVE 0")
    arduino.write(b"MOVE 0\n")
    wait_for(arduino, {"ARRIVED"})

    print("Sending RELEASE")
    arduino.write(b"RELEASE\n")
    wait_for(arduino, {"DONE"})

    arduino.close()


if __name__ == "__main__":
    main()
