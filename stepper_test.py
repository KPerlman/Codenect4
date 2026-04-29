import time
import serial


def main():
    port = "/dev/ttyACM0"
    arduino = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)
    arduino.reset_input_buffer()

    print("Sending MOVE 0")
    arduino.write(b"MOVE 0\n")
    while True:
        line = arduino.readline().decode(errors="ignore").strip()
        if line:
            print("<", line)
        if line == "ARRIVED":
            break

    print("Sending RELEASE")
    arduino.write(b"RELEASE\n")
    while True:
        line = arduino.readline().decode(errors="ignore").strip()
        if line:
            print("<", line)
        if line == "DONE":
            break

    arduino.close()


if __name__ == "__main__":
    main()
