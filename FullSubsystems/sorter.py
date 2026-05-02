import argparse
import time
import sys
from pathlib import Path
import board
import busio
from adafruit_pca9685 import PCA9685
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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

MISS_LIMIT = 3
AGITATE_SWINGS = 4
AGITATE_DELTA = 12

CLEAR_THRESH = 1786.7
RED_MARGIN = 8.0
YELLOW_CLEAR = 1940.0
YELLOW_GREEN_MIN = 900.0
YELLOW_RG_RATIO = 0.55


def move_servo(pca, channel, angle, max_angle=180, offset=0):
    corrected_angle = max(0, min(max_angle, angle + offset))
    pulse = PULSE_MIN + (corrected_angle / float(max_angle)) * (PULSE_MAX - PULSE_MIN)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def classify_color(
    sensor,
    clear_thresh,
    red_margin,
    yellow_clear,
    yellow_green_min,
    yellow_rg_ratio,
    sample_count=5,
    sample_delay=0.05,
):
    r, g, b, clear = read_sample(sensor, count=sample_count, delay_s=sample_delay)
    red_delta = r - max(g, b)
    green_ratio = g / max(r, 1.0)

    if clear < clear_thresh:
        return "none", (r, g, b, clear, red_delta, green_ratio)
    if (
        clear >= yellow_clear
        and g >= yellow_green_min
        and green_ratio >= yellow_rg_ratio
    ):
        return "yellow", (r, g, b, clear, red_delta, green_ratio)
    if red_delta >= red_margin and r > g and r > b:
        return "red", (r, g, b, clear, red_delta, green_ratio)
    return "none", (r, g, b, clear, red_delta, green_ratio)


def read_sample(sensor, count=5, delay_s=0.05):
    r_total = g_total = b_total = c_total = 0
    for _ in range(count):
        r, g, b, clear = sensor.color_raw
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


def calibrate_mode(
    pca,
    sensor,
    pickup_settle,
    detect_settle,
    drop_settle,
    drop_hold,
    sample_count,
    sample_delay,
    clear_thresh,
    red_margin,
    yellow_clear,
    yellow_green_min,
    yellow_rg_ratio,
):
    red_samples = []
    yellow_samples = []
    none_samples = []
    next_pickup_right = True

    print("Sorter calibration: label each detection while paused at DETECT.")
    print("Labels: r=red, y=yellow, n=none, q=quit")

    while True:
        pickup_angle = RIGHT_PICKUP if next_pickup_right else LEFT_PICKUP
        next_pickup_right = not next_pickup_right

        move_servo(pca, SERVO_CHANNEL, pickup_angle, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(pickup_settle)

        move_servo(pca, SERVO_CHANNEL, DETECT, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(detect_settle)

        label = input("Label [r/y/n/q]: ").strip().lower()
        if label == "q":
            break
        if label not in {"r", "y", "n"}:
            print("Use r, y, n, or q.")
            continue

        r, g, b, clear = read_sample(sensor, count=sample_count, delay_s=sample_delay)
        print(f"Sample r={r:.1f} g={g:.1f} b={b:.1f} clear={clear:.1f}")

        if label == "r":
            red_samples.append((r, g, b, clear))
            move_servo(pca, SERVO_CHANNEL, ROBOT_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(drop_settle)
            time.sleep(drop_hold)
        elif label == "y":
            yellow_samples.append((r, g, b, clear))
            move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(drop_settle)
            time.sleep(drop_hold)
        else:
            none_samples.append((r, g, b, clear))
            move_servo(pca, SERVO_CHANNEL, pickup_angle, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(drop_settle)
            time.sleep(drop_hold)

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
    suggested_clear_thresh = clear_thresh
    suggested_red_margin = red_margin
    suggested_yellow_clear = yellow_clear
    suggested_yellow_green_min = yellow_green_min
    suggested_yellow_rg_ratio = yellow_rg_ratio

    if piece_clears and none_clears:
        piece_min = min(piece_clears)
        none_max = max(none_clears)
        suggested_clear_thresh = (piece_min + none_max) / 2.0
        print(f"\nSuggested clear threshold: {suggested_clear_thresh:.1f}")
        if piece_min <= none_max:
            print("Warning: clear ranges overlap; adjust lighting or use color margins.")

    if red_samples:
        red_margins = [s[0] - max(s[1], s[2]) for s in red_samples]
        none_red_margins = [s[0] - max(s[1], s[2]) for s in none_samples]
        if none_red_margins:
            suggested_red_margin = (min(red_margins) + max(none_red_margins)) / 2.0
            print(f"Suggested red margin (r - max(g,b)): {suggested_red_margin:.1f}")
            if min(red_margins) <= max(none_red_margins):
                print("Warning: red and none red-margin ranges overlap; red separation may need tuning.")
        else:
            suggested_red_margin = min(red_margins)
            print(f"Suggested red margin (r - max(g,b)): {suggested_red_margin:.1f}")

    if yellow_samples:
        yellow_clears = [s[3] for s in yellow_samples]
        non_yellow_piece_clears = [s[3] for s in red_samples]
        if non_yellow_piece_clears:
            suggested_yellow_clear = (min(yellow_clears) + max(non_yellow_piece_clears)) / 2.0
            print(f"Suggested yellow clear threshold: {suggested_yellow_clear:.1f}")
            if min(yellow_clears) <= max(non_yellow_piece_clears):
                print("Warning: red and yellow clear ranges overlap; yellow separation may need tuning.")
        else:
            suggested_yellow_clear = min(yellow_clears)
            print(f"Suggested yellow clear threshold: {suggested_yellow_clear:.1f}")

        yellow_greens = [s[1] for s in yellow_samples]
        non_yellow_greens = [s[1] for s in red_samples]
        if non_yellow_greens:
            suggested_yellow_green_min = (min(yellow_greens) + max(non_yellow_greens)) / 2.0
            print(f"Suggested yellow green minimum: {suggested_yellow_green_min:.1f}")
            if min(yellow_greens) <= max(non_yellow_greens):
                print("Warning: yellow and non-yellow green ranges overlap; yellow separation may need tuning.")
        else:
            suggested_yellow_green_min = min(yellow_greens)
            print(f"Suggested yellow green minimum: {suggested_yellow_green_min:.1f}")

        yellow_green_ratios = [s[1] / max(s[0], 1.0) for s in yellow_samples]
        non_yellow_green_ratios = [s[1] / max(s[0], 1.0) for s in red_samples]
        if non_yellow_green_ratios:
            suggested_yellow_rg_ratio = (
                min(yellow_green_ratios) + max(non_yellow_green_ratios)
            ) / 2.0
            print(f"Suggested yellow g/r ratio minimum: {suggested_yellow_rg_ratio:.3f}")
            if min(yellow_green_ratios) <= max(non_yellow_green_ratios):
                print("Warning: yellow and non-yellow g/r ratio ranges overlap; yellow separation may need tuning.")
        else:
            suggested_yellow_rg_ratio = min(yellow_green_ratios)
            print(f"Suggested yellow g/r ratio minimum: {suggested_yellow_rg_ratio:.3f}")

    print("\nRun with:")
    print(
        "python3 FullSubsystems/sorter.py "
        f"--sensor-bus 3 "
        f"--clear-thresh {suggested_clear_thresh:.1f} "
        f"--red-margin {suggested_red_margin:.1f} "
        f"--yellow-clear {suggested_yellow_clear:.1f} "
        f"--yellow-green-min {suggested_yellow_green_min:.1f} "
        f"--yellow-rg-ratio {suggested_yellow_rg_ratio:.3f} "
        "--debug"
    )


def agitate(pca, base_angle):
    for _ in range(AGITATE_SWINGS):
        move_servo(pca, SERVO_CHANNEL, base_angle + AGITATE_DELTA, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(0.2)
        move_servo(pca, SERVO_CHANNEL, base_angle - AGITATE_DELTA, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(0.2)
    move_servo(pca, SERVO_CHANNEL, base_angle, max_angle=MAX_ANGLE, offset=OFFSET)


def main():
    parser = argparse.ArgumentParser(description="Sorter control / calibration")
    parser.add_argument("--calibrate", action="store_true", help="Run interactive calibration mode")
    parser.add_argument(
        "--sensor-bus",
        type=int,
        default=3,
        help="I2C bus number for the TCS34725 sensor (default: 3)",
    )
    parser.add_argument("--clear-thresh", type=float, default=CLEAR_THRESH)
    parser.add_argument("--red-margin", type=float, default=RED_MARGIN)
    parser.add_argument("--yellow-clear", type=float, default=YELLOW_CLEAR)
    parser.add_argument("--yellow-green-min", type=float, default=YELLOW_GREEN_MIN)
    parser.add_argument("--yellow-rg-ratio", type=float, default=YELLOW_RG_RATIO)
    parser.add_argument("--pickup-settle", type=float, default=PICKUP_SETTLE)
    parser.add_argument("--detect-settle", type=float, default=DETECT_SETTLE)
    parser.add_argument("--drop-settle", type=float, default=DROP_SETTLE)
    parser.add_argument("--drop-hold", type=float, default=DROP_HOLD)
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--sample-delay", type=float, default=0.05)
    parser.add_argument("--debug", action="store_true", help="Print step-by-step moves")
    args = parser.parse_args()

    i2c_pca = busio.I2C(board.SCL, board.SDA)

    pca = PCA9685(i2c_pca)
    pca.frequency = 50
    sensor = open_tcs34725(args.sensor_bus, integration_time_ms=100, gain=4)

    miss_count = 0
    next_pickup_right = True

    try:
        move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
        time.sleep(1.0)

        if args.calibrate:
            calibrate_mode(
                pca,
                sensor,
                pickup_settle=args.pickup_settle,
                detect_settle=args.detect_settle,
                drop_settle=args.drop_settle,
                drop_hold=args.drop_hold,
                sample_count=args.sample_count,
                sample_delay=args.sample_delay,
                clear_thresh=args.clear_thresh,
                red_margin=args.red_margin,
                yellow_clear=args.yellow_clear,
                yellow_green_min=args.yellow_green_min,
                yellow_rg_ratio=args.yellow_rg_ratio,
            )
            return

        while True:
            pickup_angle = RIGHT_PICKUP if next_pickup_right else LEFT_PICKUP
            next_pickup_right = not next_pickup_right

            if args.debug:
                print(f"Pickup -> {pickup_angle}")
            move_servo(pca, SERVO_CHANNEL, pickup_angle, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(args.pickup_settle)

            if miss_count >= MISS_LIMIT:
                agitate(pca, pickup_angle)
                time.sleep(0.2)

            if args.debug:
                print(f"Detect -> {DETECT}")
            move_servo(pca, SERVO_CHANNEL, DETECT, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(args.detect_settle)

            color, sample = classify_color(
                sensor,
                args.clear_thresh,
                args.red_margin,
                args.yellow_clear,
                args.yellow_green_min,
                args.yellow_rg_ratio,
                sample_count=args.sample_count,
                sample_delay=args.sample_delay,
            )
            if args.debug:
                r, g, b, clear, red_delta, green_ratio = sample
                print(
                    f"Sample r={r:.1f} g={g:.1f} b={b:.1f} "
                    f"clear={clear:.1f} red_delta={red_delta:.1f} "
                    f"g/r={green_ratio:.3f} -> {color}"
                )
            if color == "red":
                if args.debug:
                    print(f"Drop -> robot ({ROBOT_DROP})")
                move_servo(pca, SERVO_CHANNEL, ROBOT_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(args.drop_settle)
                time.sleep(args.drop_hold)
                miss_count = 0
            elif color == "yellow":
                if args.debug:
                    print(f"Drop -> player ({PLAYER_DROP})")
                move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(args.drop_settle)
                time.sleep(args.drop_hold)
                miss_count = 0
            else:
                if args.debug:
                    print(f"Reset -> player ({PLAYER_DROP}) after {color}")
                move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(args.drop_settle)
                miss_count += 1

    finally:
        move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
        pca.deinit()


if __name__ == "__main__":
    main()
