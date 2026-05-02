import time
import board
import busio
import adafruit_bitbangio as bitbangio
import adafruit_tcs34725


def classify_color(r, g, b, clear):
    clear_thresh = 1733.7
    red_margin = 33.0
    yellow_clear = 1800.0

    if clear < clear_thresh:
        return "no piece"
    if clear >= yellow_clear:
        return "yellow piece"
    if r - max(g, b) >= red_margin:
        return "red piece"
    return "no piece"


def main():
    try:
        i2c = busio.I2C(board.D17, board.D27)
    except ValueError:
        i2c = bitbangio.I2C(board.D27, board.D17)
    sensor = adafruit_tcs34725.TCS34725(i2c)
    sensor.integration_time = 100
    sensor.gain = 4

    print("Reading sorter color sensor on GPIO17/27. Ctrl+C to stop.")
    try:
        while True:
            r, g, b = sensor.color_rgb_bytes
            _, _, _, clear = sensor.color_raw
            result = classify_color(r, g, b, clear)
            print(f"{result} (r={r} g={g} b={b} clear={clear})")
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
