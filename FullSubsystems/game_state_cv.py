import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from connect4_vision import Connect4Tracker, list_available_cameras


PIECE_MAP = {
    0: ".",
    1: "R",
    2: "Y",
}


def is_linux():
    return sys.platform.startswith("linux")


def choose_camera(preferred_index=None, preferred_device=None, max_check=5, width=1280, height=720):
    if preferred_device is not None:
        return [preferred_device]

    if preferred_index is not None:
        if is_linux():
            return [f"/dev/video{preferred_index}"]
        return [preferred_index]

    working_cams = list_available_cameras(max_check=max_check)
    if not working_cams:
        print("No cameras found during scan. Falling back to camera 0.")
        return [0]

    scored = []
    for idx in working_cams:
        score = probe_camera(index=idx, width=width, height=height)
        if score > 0:
            scored.append((score, idx))

    if not scored:
        print(f"Cameras found: {working_cams}")
        return working_cams

    scored.sort(key=lambda item: (-item[0], item[1]))
    ordered = [idx for _, idx in scored]
    print(f"Camera candidates by stability: {ordered}")
    if len(ordered) == 1:
        print(f"Auto-selecting camera {ordered[0]}")
    return ordered


def board_to_text(board_state):
    lines = ["0 1 2 3 4 5 6"]
    for row in board_state:
        lines.append(" ".join(PIECE_MAP[int(cell)] for cell in row))
    return "\n".join(lines)


def winner_text(winner):
    if winner == 1:
        return "RED"
    if winner == 2:
        return "YELLOW"
    return "NONE"


def print_board_state(board_state, winner, tracker):
    print("\n--- CONNECT 4 STATE ---")
    print(board_to_text(board_state))
    print(f"Winner: {winner_text(winner)}")
    print(
        "Tracker: "
        f"active={tracker.is_board_active} "
        f"calibrated={tracker.is_calibrated} "
        f"coast_frames={tracker.coast_frames}"
    )


def boards_equal(left, right):
    if left is None or right is None:
        return False
    return np.array_equal(left, right)


def open_camera(source, width, height):
    if is_linux():
        cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    if cap.isOpened():
        if is_linux():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not is_linux():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def probe_camera(source, width, height, attempts=5, required_successes=3):
    cap = open_camera(source, width, height)
    if not cap.isOpened():
        return 0

    successes = 0
    try:
        time.sleep(0.2)
        for _ in range(attempts):
            ret, _ = cap.read()
            if ret:
                successes += 1
            time.sleep(0.05)
    finally:
        cap.release()

    return successes if successes >= required_successes else 0


def open_first_available_camera(candidates, width, height):
    last_error = None
    for source in candidates:
        cap = open_camera(source, width, height)
        if cap.isOpened():
            print(f"Using camera {source}. Press Ctrl+C to stop.")
            return cap, source
        last_error = RuntimeError(f"Could not open camera {source}")
    if last_error is not None:
        raise last_error
    raise RuntimeError("No camera candidates available")


def warmup_camera(cap, frames=5):
    for _ in range(frames):
        ret, _ = cap.read()
        if not ret:
            return False
        time.sleep(0.05)
    return True


def reopen_camera(source, width, height, warmup_frames=3):
    cap = open_camera(source, width, height)
    if not cap.isOpened():
        return None
    if not warmup_camera(cap, frames=warmup_frames):
        cap.release()
        return None
    return cap


def main():
    parser = argparse.ArgumentParser(
        description="Read Connect 4 board state from a USB webcam and print it in text."
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        help="Camera index to use. Defaults to auto-detect.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Explicit camera device path such as /dev/video0.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Requested camera width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Requested camera height.",
    )
    parser.add_argument(
        "--max-camera-check",
        type=int,
        default=5,
        help="How many camera indices to probe during auto-detect.",
    )
    parser.add_argument(
        "--print-every-frame",
        action="store_true",
        help="Print the board every frame instead of only when it changes.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the tracker windows while printing text state.",
    )
    parser.add_argument(
        "--fps-log",
        action="store_true",
        help="Print periodic FPS/debug info.",
    )
    parser.add_argument(
        "--read-retries",
        type=int,
        default=5,
        help="How many consecutive failed reads to tolerate before reopening the camera.",
    )
    args = parser.parse_args()

    if args.show and not os.environ.get("DISPLAY"):
        print("No DISPLAY found. Disabling --show and continuing in text-only mode.")
        args.show = False

    camera_candidates = choose_camera(
        args.camera,
        preferred_device=args.device,
        max_check=args.max_camera_check,
        width=args.width,
        height=args.height,
    )
    cap, camera_index = open_first_available_camera(
        camera_candidates,
        args.width,
        args.height,
    )

    tracker = Connect4Tracker()
    last_printed_board = None
    last_printed_winner = None
    frames = 0
    last_fps_time = time.time()
    remaining_candidates = [source for source in camera_candidates if source != camera_index]
    failed_reads = 0

    warmup_camera(cap)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                failed_reads += 1
                if failed_reads < args.read_retries:
                    time.sleep(0.1)
                    continue

                print(f"Camera frame read failed {failed_reads} times. Reopening camera {camera_index}.")
                cap.release()
                reopened = reopen_camera(camera_index, args.width, args.height)
                if reopened is not None:
                    cap = reopened
                    failed_reads = 0
                    continue

                if remaining_candidates:
                    print("Primary camera reopen failed. Trying next camera candidate.")
                    cap, camera_index = open_first_available_camera(
                        remaining_candidates,
                        args.width,
                        args.height,
                    )
                    remaining_candidates = [source for source in remaining_candidates if source != camera_index]
                    tracker = Connect4Tracker()
                    last_printed_board = None
                    last_printed_winner = None
                    failed_reads = 0
                    warmup_camera(cap)
                    continue

                print("Camera frame read failed and no camera recovered. Stopping.")
                break
            failed_reads = 0

            frame_out, mask, warped = tracker.process_frame(frame)
            board_copy = np.copy(tracker.board_state)
            should_print = args.print_every_frame or not boards_equal(board_copy, last_printed_board)
            should_print = should_print or tracker.winner != last_printed_winner

            if should_print:
                print_board_state(board_copy, tracker.winner, tracker)
                last_printed_board = board_copy
                last_printed_winner = tracker.winner

            if args.show:
                try:
                    cv2.imshow("Connect4 Main Feed", frame_out)
                    if warped is not None:
                        cv2.imshow("Connect4 Warped", warped)
                    elif mask is not None:
                        cv2.imshow("Connect4 Mask", mask)

                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        print("Quit key pressed.")
                        break
                except cv2.error as exc:
                    print(f"OpenCV display failed ({exc}). Disabling preview windows.")
                    args.show = False

            frames += 1
            if args.fps_log and time.time() - last_fps_time >= 2.0:
                elapsed = time.time() - last_fps_time
                fps = frames / elapsed if elapsed > 0 else 0.0
                print(
                    f"[debug] fps={fps:.1f} "
                    f"active={tracker.is_board_active} calibrated={tracker.is_calibrated}"
                )
                frames = 0
                last_fps_time = time.time()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
