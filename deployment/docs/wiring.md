# Wiring Notes

This is not a full electrical schematic. It is a quick reminder of the assumptions currently baked into the code.

## PCA9685 Servo Driver

- The servo code expects a PCA9685 on the Pi's normal hardware I2C bus.
- Typical pins:
  - `3.3V`
  - `GND`
  - `SDA`
  - `SCL`

## Servo Channels

Shared zero offsets are defined in `servo_config.py`:

```python
SERVO_OFFSETS = [4, 5, 4, 4, 4, 3, 0]
```

Current high-level usage:

- channels `0-5`: column/drop servos used during the game loop
- channel `6`: general sorter-related servo path

## Sorter Color Sensor

- sorter TCS34725 uses the custom sensor bus path used by `open_tcs34725(...)`
- sorter code has historically used sensor bus `3`

## Belt Color Sensor

- belt TCS34725 is intended for the GPIO `23/24` software-I2C path used by belt scripts

## Stepper Controller

- serial path expected by stepper helpers: `/dev/serial0`
- serial handshake uses `PING` / `PONG`

## USB Webcam

- game CV flow expects the main capture device to be `/dev/video0`
- common launch settings:

```bash
python3 FullSubsystems/game_state_cv.py --device /dev/video0 --width 640 --height 480 --play-vs-ai
```

## Web Dashboard

- service entrypoint: `web_control_server.py`
- default port: `8000`

If any of these assumptions change in code, update this file at the same time.
