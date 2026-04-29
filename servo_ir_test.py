import time
from robot_controller import RobotController

def main():
    robot = RobotController()

    print("Move servo to 90")
    robot.move_servo(0, 90)
    time.sleep(1)

    print("Move servo back to 0")
    robot.move_servo(0, 0)

    print("Reading IR sensor (Ctrl+C to stop)...")
    while True:
        print(robot.sensor.value)
        time.sleep(0.2)

if __name__ == "__main__":
    main()