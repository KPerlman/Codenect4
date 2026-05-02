import time
import board
import busio
from adafruit_pca9685 import PCA9685
from tcs_bus import open_tcs34725


SERVO_CHANNEL = 6
MAX_ANGLE = 270
PULSE_MIN = 500
PULSE_MAX = 2500
OFFSET = 0

PLAYER_DROP = 0
RIGHT_PICKUP = 85
LEFT_PICKUP = 165
DETECT = 200
ROBOT_DROP = 270

PICKUP_SETTLE = 0.6
DETECT_SETTLE = 0.4
DROP_SETTLE = 0.8
DROP_HOLD = 1.0


def move_servo(pca, channel, angle, max_angle=180, offset=0):
    corrected_angle = max(0, min(max_angle, angle + offset))
    pulse = PULSE_MIN + (corrected_angle / float(max_angle)) * (PULSE_MAX - PULSE_MIN)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


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


def summarize(label, samples):
    if not samples:
        return None
    rs = [s[0] for s in samples]
    gs = [s[1] for s in samples]
    bs = [s[2] for s in samples]
    cs = [s[3] for s in samples]
    return {
        "count": len(samples),
        "r_avg": sum(rs) / len(rs),
        "g_avg": sum(gs) / len(gs),
        "b_avg": sum(bs) / len(bs),
        "c_avg": sum(cs) / len(cs),
        "r_min": min(rs),
        "g_min": min(gs),
        "b_min": min(bs),
        "c_min": min(cs),
        "r_max": max(rs),
        "g_max": max(gs),
        "b_max": max(bs),
        "c_max": max(cs),
    }


def main():
    i2c_pca = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c_pca)
    pca.frequency = 50

    sensor = open_tcs34725(3, integration_time_ms=100, gain=4)

    red_samples = []
    yellow_samples = []
    none_samples = []

    next_pickup_right = True

    print("Sorter calibration: label each detection while paused at DETECT.")
    print("Labels: r=red, y=yellow, n=none, q=quit")

    try:
        move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(1.0)

        while True:
            pickup_angle = RIGHT_PICKUP if next_pickup_right else LEFT_PICKUP
            next_pickup_right = not next_pickup_right

            move_servo(pca, SERVO_CHANNEL, pickup_angle, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(PICKUP_SETTLE)

            move_servo(pca, SERVO_CHANNEL, DETECT, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(DETECT_SETTLE)

            label = input("Label [r/y/n/q]: ").strip().lower()
            if label == "q":
                break
            if label not in {"r", "y", "n"}:
                print("Use r, y, n, or q.")
                continue

            r, g, b, clear = read_sample(sensor)
            print(f"Sample r={r:.1f} g={g:.1f} b={b:.1f} clear={clear:.1f}")

            if label == "r":
                red_samples.append((r, g, b, clear))
                move_servo(pca, SERVO_CHANNEL, ROBOT_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(DROP_SETTLE)
                time.sleep(DROP_HOLD)
            elif label == "y":
                yellow_samples.append((r, g, b, clear))
                move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(DROP_SETTLE)
                time.sleep(DROP_HOLD)
            else:
                none_samples.append((r, g, b, clear))
                move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(DROP_SETTLE)
                time.sleep(DROP_HOLD)

    finally:
        move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
        pca.deinit()

    red_stats = summarize("red", red_samples)
    yellow_stats = summarize("yellow", yellow_samples)
    none_stats = summarize("none", none_samples)

    print("\n--- Summary ---")
    for name, stats in [("red", red_stats), ("yellow", yellow_stats), ("none", none_stats)]:
        if not stats:
            print(f"{name}: no samples")
            continue
        print(
            f"{name}: count={stats['count']} "
            f"avg(r,g,b,c)=({stats['r_avg']:.1f},{stats['g_avg']:.1f},"
            f"{stats['b_avg']:.1f},{stats['c_avg']:.1f}) "
            f"clear_range=({stats['c_min']:.1f}-{stats['c_max']:.1f})"
        )

    piece_clears = [s[3] for s in red_samples + yellow_samples]
    none_clears = [s[3] for s in none_samples]
    if piece_clears and none_clears:
        piece_min = min(piece_clears)
        none_max = max(none_clears)
        clear_thresh = (piece_min + none_max) / 2.0
        print(f"\nSuggested clear threshold: {clear_thresh:.1f}")
        if piece_min <= none_max:
            print("Warning: clear ranges overlap; adjust lighting or use color margins.")

    if red_samples:
        red_margins = [s[0] - max(s[1], s[2]) for s in red_samples]
        print(f"Suggested red margin (r - max(g,b)): {min(red_margins):.1f}")

    if yellow_samples:
        yellow_margins = [s[1] - max(s[0], s[2]) for s in yellow_samples]
        print(f"Suggested yellow margin (g - max(r,b)): {min(yellow_margins):.1f}")


if __name__ == "__main__":
    main()
