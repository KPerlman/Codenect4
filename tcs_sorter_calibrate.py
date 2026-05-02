import time
import board
import busio
import adafruit_tcs34725
import adafruit_bitbangio as bitbangio


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
    try:
        i2c = busio.I2C(board.D17, board.D27)
    except ValueError:
        i2c = bitbangio.I2C(board.D27, board.D17)

    sensor = adafruit_tcs34725.TCS34725(i2c)
    sensor.integration_time = 100
    sensor.gain = 4

    red_samples = []
    yellow_samples = []
    none_samples = []

    print("TCS34725 sorter calibration on GPIO17/27")
    print("Label each sample: r=red, y=yellow, n=none, q=quit")

    try:
        while True:
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
            elif label == "y":
                yellow_samples.append((r, g, b, clear))
            else:
                none_samples.append((r, g, b, clear))
    finally:
        pass

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

    # Suggested thresholds
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
