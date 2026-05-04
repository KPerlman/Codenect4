import argparse
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from FullSubsystems.belt import open_belt_tcs34725


def read_average(sensor, count=10, delay_s=0.05):
    r_total = g_total = b_total = c_total = 0.0
    for _ in range(count):
        r, g, b, clear = sensor.color_raw
        r_total += r
        g_total += g
        b_total += b
        c_total += clear
        time.sleep(delay_s)
    return {
        "r": r_total / count,
        "g": g_total / count,
        "b": b_total / count,
        "clear": c_total / count,
    }


def summarize(samples, key):
    values = [sample[key] for sample in samples]
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
    }


def suggest_threshold(empty_samples, piece_samples, key):
    empty_max = max(sample[key] for sample in empty_samples)
    piece_min = min(sample[key] for sample in piece_samples)
    threshold = (empty_max + piece_min) / 2.0
    overlap = piece_min <= empty_max
    return {
        "threshold": threshold,
        "empty_max": empty_max,
        "piece_min": piece_min,
        "overlap": overlap,
    }


def collect_state(sensor, label, rounds, samples_per_round, sample_delay):
    collected = []
    for idx in range(1, rounds + 1):
        input(f"{label} sample {idx}/{rounds}: set up the sensor and press Enter...")
        sample = read_average(sensor, count=samples_per_round, delay_s=sample_delay)
        collected.append(sample)
        print(
            f"  r={sample['r']:.1f} g={sample['g']:.1f} "
            f"b={sample['b']:.1f} clear={sample['clear']:.1f}"
        )
    return collected


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate belt TCS34725 thresholds from empty vs piece-covered readings"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=6,
        help="Number of averaged samples to collect for each state",
    )
    parser.add_argument(
        "--samples-per-round",
        type=int,
        default=10,
        help="Raw TCS reads to average for each collected sample",
    )
    parser.add_argument(
        "--sample-delay",
        type=float,
        default=0.05,
        help="Delay between raw reads inside each averaged sample",
    )
    args = parser.parse_args()

    sensor = open_belt_tcs34725(integration_time_ms=100, gain=4)

    print("Belt TCS threshold calibration")
    print("This script compares EMPTY readings against PIECE-COVERED readings.")
    print("It will suggest thresholds from the midpoint between empty max and piece min.")
    print()
    print("Note: the current belt runtime uses the RED channel threshold (`--r-thresh`).")
    print("This script will also show CLEAR-channel stats for comparison.")
    print()

    empty_samples = collect_state(
        sensor,
        label="EMPTY",
        rounds=args.rounds,
        samples_per_round=args.samples_per_round,
        sample_delay=args.sample_delay,
    )
    print()
    piece_samples = collect_state(
        sensor,
        label="PIECE-COVERED",
        rounds=args.rounds,
        samples_per_round=args.samples_per_round,
        sample_delay=args.sample_delay,
    )

    red_empty = summarize(empty_samples, "r")
    red_piece = summarize(piece_samples, "r")
    clear_empty = summarize(empty_samples, "clear")
    clear_piece = summarize(piece_samples, "clear")

    red_suggestion = suggest_threshold(empty_samples, piece_samples, "r")
    clear_suggestion = suggest_threshold(empty_samples, piece_samples, "clear")

    print("\n--- Summary ---")
    print(
        f"RED   empty avg={red_empty['avg']:.1f} range=({red_empty['min']:.1f}-{red_empty['max']:.1f})"
    )
    print(
        f"RED   piece avg={red_piece['avg']:.1f} range=({red_piece['min']:.1f}-{red_piece['max']:.1f})"
    )
    print(
        f"CLEAR empty avg={clear_empty['avg']:.1f} range=({clear_empty['min']:.1f}-{clear_empty['max']:.1f})"
    )
    print(
        f"CLEAR piece avg={clear_piece['avg']:.1f} range=({clear_piece['min']:.1f}-{clear_piece['max']:.1f})"
    )

    print("\n--- Suggestions ---")
    print(
        f"Suggested RED threshold:   {red_suggestion['threshold']:.1f} "
        f"(empty max {red_suggestion['empty_max']:.1f}, piece min {red_suggestion['piece_min']:.1f})"
    )
    if red_suggestion["overlap"]:
        print("Warning: RED ranges overlap. Detection may be noisy; improve lighting or piece placement.")

    print(
        f"Suggested CLEAR threshold: {clear_suggestion['threshold']:.1f} "
        f"(empty max {clear_suggestion['empty_max']:.1f}, piece min {clear_suggestion['piece_min']:.1f})"
    )
    if clear_suggestion["overlap"]:
        print("Warning: CLEAR ranges overlap. Detection may be noisy; improve lighting or piece placement.")

    print("\nRun belt with:")
    print(f"python3 FullSubsystems/belt.py --r-thresh {red_suggestion['threshold']:.1f}")


if __name__ == "__main__":
    main()
