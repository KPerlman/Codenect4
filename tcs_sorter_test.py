import time
from tcs_bus import open_tcs34725


def classify_color(r, g, b, clear):
    clear_thresh = 1786.7
    red_margin = 8.0
    yellow_clear = 1940.0

    red_delta = r - max(g, b)

    if clear < clear_thresh:
        return "no piece"
    if clear >= yellow_clear:
        return "yellow piece"
    if red_delta >= red_margin and r > g and r > b:
        return "red piece"
    return "no piece"


def main():
    sensor = open_tcs34725(3, integration_time_ms=100, gain=4)

    print("Reading sorter color sensor on GPIO17/27. Ctrl+C to stop.")
    try:
        while True:
            r, g, b, clear = sensor.color_raw
            result = classify_color(r, g, b, clear)
            print(f"{result} (r={r} g={g} b={b} clear={clear})")
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
