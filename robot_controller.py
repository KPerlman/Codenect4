import time
import serial
import board
import busio
from adafruit_pca9685 import PCA9685
import adafruit_tcs34725

class RobotController:
    def __init__(self):
        self.i2c_pca = busio.I2C(board.SCL, board.SDA)
        self.i2c_top = busio.I2C(board.D17, board.D27)
        self.i2c_bottom = busio.I2C(board.D23, board.D24)

        self.pca = PCA9685(self.i2c_pca)
        self.pca.frequency = 50

        self.top_color = adafruit_tcs34725.TCS34725(self.i2c_top)
        self.top_color.integration_time = 100
        self.top_color.gain = 4
        self.top_clear_baseline = self._calibrate_clear_baseline(self.top_color)
        self.top_clear_delta = 500
        # Setup serial connection to Arduino
        self.arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
        self.offsets = [1, 6, 10, 6, 15, 2, 0]

    def _calibrate_clear_baseline(self, sensor):
        samples = []
        for _ in range(10):
            samples.append(sensor.clear)
            time.sleep(0.02)
        return sum(samples) / len(samples)

    def _top_piece_detected(self):
        return self.top_color.clear > (self.top_clear_baseline + self.top_clear_delta)

    def move_servo(self, channel, angle):
        corrected_angle = max(0, min(180, angle + self.offsets[channel]))
        pulse_min = 450
        pulse_max = 2550
        pulse = pulse_min + (corrected_angle / 180.0) * (pulse_max - pulse_min)
        self.pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)

    def drop_piece(self, col):
        # Tell Arduino to move the stepper
        self.arduino.write(f"MOVE {col}\n".encode())

        # Wait for Arduino to confirm the piece is at the top
        arrival_deadline = time.time() + 10.0
        while True:
            if time.time() > arrival_deadline:
                raise TimeoutError("Stepper did not report ARRIVED in time")

            response = self.arduino.readline().decode().strip()
            if response == "ARRIVED":
                break
            time.sleep(0.05)

        # Flip the servo for the chosen column
        self.move_servo(col, 90)

        # Wait for top color sensor confirmation
        detection_start = None
        sensor_deadline = time.time() + 5.0
        while True:
            if time.time() > sensor_deadline:
                raise TimeoutError("Top color sensor did not confirm piece drop")

            if self._top_piece_detected():
                if detection_start is None:
                    detection_start = time.time()
                if time.time() - detection_start >= 0.5:
                    break
            else:
                detection_start = None
            time.sleep(0.05)

        # Reset the servo
        self.move_servo(col, 0)

        # Tell Arduino it is safe to return
        self.arduino.write("RELEASE\n".encode())
        done_deadline = time.time() + 10.0
        while True:
            if time.time() > done_deadline:
                raise TimeoutError("Stepper did not report DONE in time")

            response = self.arduino.readline().decode().strip()
            if response == "DONE":
                break
            time.sleep(0.05)
