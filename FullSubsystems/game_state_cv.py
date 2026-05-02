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
from minimax import Minimax


PIECE_MAP = {
    0: ".",
    1: "R",
    2: "Y",
}

AI_PIECE = 1
HUMAN_PIECE = 2


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
        return ["/dev/video0"] if is_linux() else [0]

    scored = []
    for idx in working_cams:
        source = f"/dev/video{idx}" if is_linux() else idx
        score = probe_camera(source=source, width=width, height=height)
        if score > 0:
            scored.append((score, source))

    if not scored:
        print(f"Cameras found: {working_cams}")
        if is_linux():
            return [f"/dev/video{idx}" for idx in working_cams]
        return working_cams

    scored.sort(key=lambda item: (-item[0], item[1]))
    ordered = [source for _, source in scored]
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


def count_piece(board_state, piece):
    return int(np.count_nonzero(board_state == piece))


def board_full(board_state):
    return not np.any(board_state == 0)


def board_winner(board_state):
    rows, cols = board_state.shape

    for r in range(rows):
        for c in range(cols - 3):
            val = int(board_state[r, c])
            if val != 0 and all(int(board_state[r, c + offset]) == val for offset in range(4)):
                return val

    for r in range(rows - 3):
        for c in range(cols):
            val = int(board_state[r, c])
            if val != 0 and all(int(board_state[r + offset, c]) == val for offset in range(4)):
                return val

    for r in range(rows - 3):
        for c in range(cols - 3):
            val = int(board_state[r, c])
            if val != 0 and all(int(board_state[r + offset, c + offset]) == val for offset in range(4)):
                return val

    for r in range(3, rows):
        for c in range(cols - 3):
            val = int(board_state[r, c])
            if val != 0 and all(int(board_state[r - offset, c + offset]) == val for offset in range(4)):
                return val

    return 0


def is_single_piece_addition(previous_board, current_board, piece):
    if previous_board is None or current_board is None:
        return False

    diffs = np.argwhere(previous_board != current_board)
    if len(diffs) != 1:
        return False

    row, col = diffs[0]
    return previous_board[row, col] == 0 and current_board[row, col] == piece


def vision_board_to_minimax(board_state):
    char_board = []
    for r in range(board_state.shape[0] - 1, -1, -1):
        row = []
        for c in range(board_state.shape[1]):
            value = int(board_state[r, c])
            if value == AI_PIECE:
                row.append("x")
            elif value == HUMAN_PIECE:
                row.append("o")
            else:
                row.append(" ")
        char_board.append(row)
    return char_board


def minimax_board_to_vision(char_board):
    board = np.zeros((6, 7), dtype=int)
    for mr, row in enumerate(char_board):
        vr = 5 - mr
        for c, value in enumerate(row):
            if value == "x":
                board[vr, c] = AI_PIECE
            elif value == "o":
                board[vr, c] = HUMAN_PIECE
    return board


def compute_ai_move(board_state, depth):
    minimax_board = vision_board_to_minimax(board_state)
    solver = Minimax(minimax_board)
    move, score = solver.bestMove(depth, minimax_board, "x")
    if move is None:
        return None, None, score
    expected_board = solver.makeMove(minimax_board, move, "x")
    return move, minimax_board_to_vision(expected_board), score


def print_ai_instruction(column, score, expected_board):
    print(f"\nComputer move: place a RED piece in column {column} (score={score}).")
    print("Expected board after RED move:")
    print(board_to_text(expected_board))


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
    parser.add_argument(
        "--play-vs-ai",
        action="store_true",
        help="Play as YELLOW against the computer using the webcam-tracked board state.",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=5,
        help="Minimax search depth for AI move selection.",
    )
    parser.add_argument(
        "--state-streak",
        type=int,
        default=3,
        help="How many identical tracker states in a row are required before game logic accepts a board update.",
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
    last_seen_board = None
    stable_streak = 0
    stable_board = None
    stable_printed_board = None
    confirmed_board = None
    game_state = "waiting_human"
    ai_expected_board = None
    ai_move_col = None
    calibration_announced = False
    waiting_ai_notice = False

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
            if boards_equal(board_copy, last_seen_board):
                stable_streak += 1
            else:
                last_seen_board = np.copy(board_copy)
                stable_streak = 1

            if stable_streak >= args.state_streak:
                stable_board = np.copy(board_copy)

            if not args.play_vs_ai:
                should_print = args.print_every_frame or not boards_equal(board_copy, last_printed_board)
                should_print = should_print or tracker.winner != last_printed_winner

                if should_print:
                    print_board_state(board_copy, tracker.winner, tracker)
                    last_printed_board = board_copy
                    last_printed_winner = tracker.winner
            else:
                if not tracker.is_calibrated:
                    if not calibration_announced:
                        print("Waiting for tracker calibration before starting play...")
                        calibration_announced = True
                elif stable_board is not None:
                    if confirmed_board is None:
                        confirmed_board = np.copy(stable_board)
                        print_board_state(confirmed_board, tracker.winner, tracker)
                        print("\nYou are YELLOW and go first.")
                        print("Make your move on the real board. The script will detect it automatically.")
                        stable_printed_board = np.copy(confirmed_board)
                    elif not boards_equal(stable_board, stable_printed_board):
                        print_board_state(stable_board, tracker.winner, tracker)
                        stable_printed_board = np.copy(stable_board)

                    if game_state == "waiting_human":
                        if is_single_piece_addition(confirmed_board, stable_board, HUMAN_PIECE):
                            confirmed_board = np.copy(stable_board)
                            if board_winner(confirmed_board) == HUMAN_PIECE:
                                print("\nYELLOW wins.")
                                break
                            if board_full(confirmed_board):
                                print("\nBoard is full. Draw.")
                                break

                            ai_move_col, ai_expected_board, score = compute_ai_move(confirmed_board, args.depth)
                            if ai_move_col is None or ai_expected_board is None:
                                print("\nNo legal AI move found. Game over.")
                                break

                            print_ai_instruction(ai_move_col, score, ai_expected_board)
                            input("Place the RED piece there, then press Enter to continue...")
                            game_state = "waiting_ai_confirmation"
                            waiting_ai_notice = False
                    elif game_state == "waiting_ai_confirmation":
                        if boards_equal(stable_board, ai_expected_board):
                            confirmed_board = np.copy(stable_board)
                            if board_winner(confirmed_board) == AI_PIECE:
                                print("\nRED wins.")
                                break
                            if board_full(confirmed_board):
                                print("\nBoard is full. Draw.")
                                break
                            print("\nRED move confirmed by vision. Your turn again.")
                            game_state = "waiting_human"
                        elif not waiting_ai_notice:
                            print(
                                "\nWaiting for the RED piece to appear in the expected column. "
                                "If the board does not match, adjust the piece and hold still."
                            )
                            waiting_ai_notice = True

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
