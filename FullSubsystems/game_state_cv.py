import argparse
import os
import sys
import time
import threading
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


def user_visible_column(board_state, column):
    return board_state.shape[1] - 1 - column


def internal_column_from_user(board_state, visible_column):
    return board_state.shape[1] - 1 - visible_column


def board_to_text(board_state):
    mirrored = np.fliplr(board_state)
    lines = ["6 5 4 3 2 1 0"]
    for row in mirrored:
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


def has_support(board_state, row, col):
    return row == board_state.shape[0] - 1 or board_state[row + 1, col] != 0


def find_single_added_piece(previous_board, current_board, piece):
    if previous_board is None or current_board is None:
        return None

    diffs = np.argwhere(previous_board != current_board)
    if len(diffs) != 1:
        return None

    row, col = diffs[0]
    if previous_board[row, col] == 0 and current_board[row, col] == piece:
        return int(row), int(col)
    return None


def legal_human_transition(previous_board, current_board):
    added = find_single_added_piece(previous_board, current_board, HUMAN_PIECE)
    if added is None:
        return False, "Expected exactly one new YELLOW piece."

    row, col = added
    if not has_support(current_board, row, col):
        return False, "YELLOW piece is floating without support."

    prev_red = count_piece(previous_board, AI_PIECE)
    prev_yellow = count_piece(previous_board, HUMAN_PIECE)
    curr_red = count_piece(current_board, AI_PIECE)
    curr_yellow = count_piece(current_board, HUMAN_PIECE)

    if curr_red != prev_red:
        return False, "RED pieces changed during YELLOW's turn."
    if curr_yellow != prev_yellow + 1:
        return False, "YELLOW must add exactly one piece."
    if curr_yellow != curr_red + 1:
        return False, "After YELLOW's turn, yellow count must be exactly one ahead of red."

    return True, f"Accepted YELLOW move in column {user_visible_column(current_board, col)}."


def legal_ai_transition(previous_board, current_board):
    added = find_single_added_piece(previous_board, current_board, AI_PIECE)
    if added is None:
        return False, "Expected exactly one new RED piece."

    row, col = added
    if not has_support(current_board, row, col):
        return False, "RED piece is floating without support."

    prev_red = count_piece(previous_board, AI_PIECE)
    prev_yellow = count_piece(previous_board, HUMAN_PIECE)
    curr_red = count_piece(current_board, AI_PIECE)
    curr_yellow = count_piece(current_board, HUMAN_PIECE)

    if curr_yellow != prev_yellow:
        return False, "YELLOW pieces changed during RED's turn."
    if curr_red != prev_red + 1:
        return False, "RED must add exactly one piece."
    if curr_red != curr_yellow:
        return False, "After RED's turn, red and yellow counts must match."

    return True, f"Accepted RED move in column {user_visible_column(current_board, col)}."


def board_distance(left, right):
    return int(np.count_nonzero(left != right))


def apply_move_to_board(board_state, piece, column):
    if column < 0 or column >= board_state.shape[1]:
        return None

    next_board = np.copy(board_state)
    for row in range(board_state.shape[0] - 1, -1, -1):
        if next_board[row, column] == 0:
            next_board[row, column] = piece
            return next_board
    return None


def legal_next_boards(board_state, piece):
    candidates = []
    for column in range(board_state.shape[1]):
        next_board = apply_move_to_board(board_state, piece, column)
        if next_board is not None:
            candidates.append((column, next_board))
    return candidates


def infer_most_likely_move(previous_board, observed_board, piece):
    candidates = legal_next_boards(previous_board, piece)
    if not candidates:
        return None

    scored = []
    for column, candidate_board in candidates:
        scored.append((board_distance(candidate_board, observed_board), column, candidate_board))
    scored.sort(key=lambda item: (item[0], item[1]))

    best_distance, best_column, best_board = scored[0]
    second_distance = scored[1][0] if len(scored) > 1 else None

    confident = False
    if best_distance == 0:
        confident = True
    elif second_distance is None and best_distance <= 2:
        confident = True
    elif second_distance is not None and best_distance + 1 < second_distance:
        confident = True

    return {
        "column": best_column,
        "board": best_board,
        "distance": best_distance,
        "second_distance": second_distance,
        "confident": confident,
    }


def parse_visible_manual_move(previous_board, piece, raw_value):
    raw = raw_value.strip().lower()
    if raw in {"", "wait", "w"}:
        return None
    try:
        visible_column = int(raw)
    except ValueError:
        return "invalid"
    if visible_column < 0 or visible_column >= previous_board.shape[1]:
        return "invalid"

    internal_column = internal_column_from_user(previous_board, visible_column)
    next_board = apply_move_to_board(previous_board, piece, internal_column)
    if next_board is None:
        return "invalid"
    return visible_column, internal_column, next_board


def prompt_manual_move(previous_board, piece, prompt_label):
    while True:
        raw = input(
            f"Vision is uncertain. Enter the actual {prompt_label} move column (0-6), "
            "or type 'wait' to keep watching: "
        )
        parsed = parse_visible_manual_move(previous_board, piece, raw)
        if parsed is None:
            return None
        if parsed == "invalid":
            print("Enter a column number 0-6, or 'wait'.")
            continue
        visible_column, _, next_board = parsed
        return visible_column, next_board


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


def compute_ai_move_with_animation(board_state, depth):
    result = {}

    def worker():
        result["value"] = compute_ai_move(board_state, depth)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    frames = ["Thinking   ", "Thinking.  ", "Thinking.. ", "Thinking..."]
    index = 0
    while thread.is_alive():
        print(f"\r{frames[index % len(frames)]}", end="", flush=True)
        time.sleep(0.25)
        index += 1
    thread.join()
    print("\r" + (" " * 16) + "\r", end="", flush=True)
    return result["value"]


def print_ai_instruction(column, score, expected_board):
    print(
        "\nComputer move: place a RED piece in column "
        f"{user_visible_column(expected_board, column)} (score={score})."
    )
    print("Expected board after RED move:")
    print(board_to_text(expected_board))


def accept_confirmed_ai_move(confirmed_board, ai_expected_board):
    confirmed_board = np.copy(ai_expected_board)
    print("\nRED move accepted on user confirmation. Your turn again.")
    return confirmed_board


def confirm_detected_human_move(previous_board, detected_board):
    added = find_single_added_piece(previous_board, detected_board, HUMAN_PIECE)
    if added is None:
        return detected_board

    _, internal_col = added
    visible_col = user_visible_column(detected_board, internal_col)
    while True:
        raw = input(
            f"Detected YELLOW in column {visible_col}. "
            "Press Enter/y to confirm, or type the correct column (0-6): "
        ).strip().lower()
        if raw in {"", "y", "yes"}:
            return detected_board

        parsed = parse_visible_manual_move(previous_board, HUMAN_PIECE, raw)
        if parsed == "invalid":
            print("Enter a column number 0-6, or press Enter to confirm the detected move.")
            continue
        if parsed is None:
            return detected_board

        visible_column, _, corrected_board = parsed
        print(f"Using manually confirmed YELLOW move in column {visible_column}.")
        return corrected_board


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


def source_exists(source):
    if isinstance(source, str) and source.startswith("/dev/"):
        return os.path.exists(source)
    return True


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


def poll_console_line():
    if not sys.stdin or sys.stdin.closed:
        return None
    try:
        if is_linux():
            import select

            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if ready:
                return sys.stdin.readline()
        return None
    except Exception:
        return None


def reopen_camera(source, width, height, warmup_frames=3, attempts=8, delay_s=0.4):
    for _ in range(attempts):
        if not source_exists(source):
            time.sleep(delay_s)
            continue

        cap = open_camera(source, width, height)
        if not cap.isOpened():
            cap.release()
            time.sleep(delay_s)
            continue
        if not warmup_camera(cap, frames=warmup_frames):
            cap.release()
            time.sleep(delay_s)
            continue
        return cap
    return None


def sync_tracker_state(tracker, board_state):
    tracker.board_state = np.copy(board_state)


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
        "--reopen-attempts",
        type=int,
        default=8,
        help="How many times to retry reopening a failed camera before giving up on it.",
    )
    parser.add_argument(
        "--reopen-delay",
        type=float,
        default=0.4,
        help="Delay in seconds between reopen attempts for a failed camera.",
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
    parser.add_argument(
        "--illegal-retries",
        type=int,
        default=4,
        help="How many uncertain board updates to tolerate before asking for manual move confirmation.",
    )
    parser.add_argument(
        "--inference-hold",
        type=int,
        default=6,
        help="How many stable frames of the same confident inferred move to wait before accepting it.",
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
    illegal_notice = None
    human_illegal_retries = 0
    ai_illegal_retries = 0
    last_rejected_human_board = None
    last_rejected_ai_board = None
    last_human_inference_key = None
    last_ai_inference_key = None
    human_inference_hold = 0
    ai_inference_hold = 0

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
                reopened = reopen_camera(
                    camera_index,
                    args.width,
                    args.height,
                    attempts=args.reopen_attempts,
                    delay_s=args.reopen_delay,
                )
                if reopened is not None:
                    cap = reopened
                    failed_reads = 0
                    warmup_camera(cap)
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
                    pending_line = poll_console_line()
                    if confirmed_board is None:
                        confirmed_board = np.copy(stable_board)
                        print_board_state(confirmed_board, tracker.winner, tracker)
                        print("\nYou are YELLOW and go first.")
                        print("Make your move on the real board. The script will detect it automatically.")
                        print("If vision is slow or wrong, type your YELLOW column (0-6) and press Enter.")
                        stable_printed_board = np.copy(confirmed_board)
                    elif not boards_equal(stable_board, stable_printed_board):
                        print_board_state(stable_board, tracker.winner, tracker)
                        stable_printed_board = np.copy(stable_board)

                    if game_state == "waiting_human":
                        if pending_line is not None:
                            parsed_manual = parse_visible_manual_move(confirmed_board, HUMAN_PIECE, pending_line)
                            if parsed_manual == "invalid":
                                print("Manual input should be a visible column number 0-6.")
                            elif parsed_manual is not None:
                                visible_col, _, manual_board = parsed_manual
                                confirmed_board = np.copy(manual_board)
                                sync_tracker_state(tracker, confirmed_board)
                                last_seen_board = np.copy(confirmed_board)
                                stable_board = np.copy(confirmed_board)
                                stable_streak = args.state_streak
                                stable_printed_board = None
                                illegal_notice = None
                                human_illegal_retries = 0
                                last_rejected_human_board = None
                                last_human_inference_key = None
                                human_inference_hold = 0
                                print(f"Manual YELLOW move recorded in column {visible_col}.")
                                if board_winner(confirmed_board) == HUMAN_PIECE:
                                    print("\nYELLOW wins.")
                                    break
                                if board_full(confirmed_board):
                                    print("\nBoard is full. Draw.")
                                    break

                                ai_move_col, ai_expected_board, score = compute_ai_move_with_animation(
                                    confirmed_board,
                                    args.depth,
                                )
                                if ai_move_col is None or ai_expected_board is None:
                                    print("\nNo legal AI move found. Game over.")
                                    break

                                print_ai_instruction(ai_move_col, score, ai_expected_board)
                                input("Place the RED piece there, then press Enter to continue...")
                                confirmed_board = accept_confirmed_ai_move(confirmed_board, ai_expected_board)
                                sync_tracker_state(tracker, confirmed_board)
                                last_seen_board = np.copy(confirmed_board)
                                stable_board = np.copy(confirmed_board)
                                stable_streak = args.state_streak
                                if board_winner(confirmed_board) == AI_PIECE:
                                    print("\nRED wins.")
                                    break
                                if board_full(confirmed_board):
                                    print("\nBoard is full. Draw.")
                                    break
                                illegal_notice = None
                                ai_illegal_retries = 0
                                last_rejected_ai_board = None
                                last_ai_inference_key = None
                                ai_inference_hold = 0
                                stable_printed_board = None
                                game_state = "waiting_human"
                                waiting_ai_notice = False
                                continue

                        is_legal, message = legal_human_transition(confirmed_board, stable_board)
                        if is_legal:
                            confirmed_board = np.copy(confirm_detected_human_move(confirmed_board, stable_board))
                            sync_tracker_state(tracker, confirmed_board)
                            last_seen_board = np.copy(confirmed_board)
                            stable_board = np.copy(confirmed_board)
                            stable_streak = args.state_streak
                            illegal_notice = None
                            human_illegal_retries = 0
                            last_rejected_human_board = None
                            last_human_inference_key = None
                            human_inference_hold = 0
                            print(message)
                            if board_winner(confirmed_board) == HUMAN_PIECE:
                                print("\nYELLOW wins.")
                                break
                            if board_full(confirmed_board):
                                print("\nBoard is full. Draw.")
                                break

                            ai_move_col, ai_expected_board, score = compute_ai_move_with_animation(
                                confirmed_board,
                                args.depth,
                            )
                            if ai_move_col is None or ai_expected_board is None:
                                print("\nNo legal AI move found. Game over.")
                                break

                            print_ai_instruction(ai_move_col, score, ai_expected_board)
                            input("Place the RED piece there, then press Enter to continue...")
                            confirmed_board = accept_confirmed_ai_move(confirmed_board, ai_expected_board)
                            sync_tracker_state(tracker, confirmed_board)
                            last_seen_board = np.copy(confirmed_board)
                            stable_board = np.copy(confirmed_board)
                            stable_streak = args.state_streak
                            if board_winner(confirmed_board) == AI_PIECE:
                                print("\nRED wins.")
                                break
                            if board_full(confirmed_board):
                                print("\nBoard is full. Draw.")
                                break
                            illegal_notice = None
                            ai_illegal_retries = 0
                            last_rejected_ai_board = None
                            last_ai_inference_key = None
                            ai_inference_hold = 0
                            stable_printed_board = None
                            game_state = "waiting_human"
                            waiting_ai_notice = False
                        elif not boards_equal(confirmed_board, stable_board):
                            if message != illegal_notice:
                                print(f"\nIgnoring illegal board update on YELLOW's turn: {message}")
                                print("This usually means at least one real piece has been played, but vision is uncertain.")
                                illegal_notice = message
                            if not boards_equal(stable_board, last_rejected_human_board):
                                human_illegal_retries += 1
                                last_rejected_human_board = np.copy(stable_board)

                            inferred = infer_most_likely_move(confirmed_board, stable_board, HUMAN_PIECE)
                            if inferred is not None:
                                inference_key = (
                                    inferred["column"],
                                    inferred["distance"],
                                    inferred["second_distance"],
                                    inferred["confident"],
                                )
                                if inference_key == last_human_inference_key:
                                    human_inference_hold += 1
                                else:
                                    last_human_inference_key = inference_key
                                    human_inference_hold = 1
                                    print(
                                        "Most likely YELLOW move guess: "
                                        f"column {inferred['column']} "
                                        f"(distance={inferred['distance']}, "
                                        f"second={inferred['second_distance']}, "
                                        f"confident={inferred['confident']})"
                                    )

                                if inferred["confident"] and human_inference_hold >= args.inference_hold:
                                    confirmed_board = np.copy(inferred["board"])
                                    illegal_notice = None
                                    human_illegal_retries = 0
                                    last_rejected_human_board = None
                                    last_human_inference_key = None
                                    human_inference_hold = 0
                                    print(
                                        "Accepting inferred YELLOW move in column "
                                        f"{user_visible_column(confirmed_board, inferred['column'])}."
                                    )
                                    sync_tracker_state(tracker, confirmed_board)
                                    last_seen_board = np.copy(confirmed_board)
                                    stable_board = np.copy(confirmed_board)
                                    stable_streak = args.state_streak
                                    if board_winner(confirmed_board) == HUMAN_PIECE:
                                        print("\nYELLOW wins.")
                                        break
                                    if board_full(confirmed_board):
                                        print("\nBoard is full. Draw.")
                                        break

                                    ai_move_col, ai_expected_board, score = compute_ai_move_with_animation(
                                        confirmed_board,
                                        args.depth,
                                    )
                                    if ai_move_col is None or ai_expected_board is None:
                                        print("\nNo legal AI move found. Game over.")
                                        break

                                    print_ai_instruction(ai_move_col, score, ai_expected_board)
                                    input("Place the RED piece there, then press Enter to continue...")
                                    confirmed_board = accept_confirmed_ai_move(confirmed_board, ai_expected_board)
                                    sync_tracker_state(tracker, confirmed_board)
                                    last_seen_board = np.copy(confirmed_board)
                                    stable_board = np.copy(confirmed_board)
                                    stable_streak = args.state_streak
                                    if board_winner(confirmed_board) == AI_PIECE:
                                        print("\nRED wins.")
                                        break
                                    if board_full(confirmed_board):
                                        print("\nBoard is full. Draw.")
                                        break
                                    illegal_notice = None
                                    ai_illegal_retries = 0
                                    last_rejected_ai_board = None
                                    last_ai_inference_key = None
                                    ai_inference_hold = 0
                                    stable_printed_board = None
                                    game_state = "waiting_human"
                                    waiting_ai_notice = False
                                    continue

                            if human_illegal_retries >= args.illegal_retries:
                                manual = prompt_manual_move(confirmed_board, HUMAN_PIECE, "YELLOW")
                                if manual is not None:
                                    manual_col, manual_board = manual
                                    confirmed_board = manual_board
                                    sync_tracker_state(tracker, confirmed_board)
                                    last_seen_board = np.copy(confirmed_board)
                                    stable_board = np.copy(confirmed_board)
                                    stable_streak = args.state_streak
                                    illegal_notice = None
                                    human_illegal_retries = 0
                                    last_rejected_human_board = None
                                    last_human_inference_key = None
                                    human_inference_hold = 0
                                    print(f"Manual YELLOW move recorded in column {manual_col}.")
                                    if board_winner(confirmed_board) == HUMAN_PIECE:
                                        print("\nYELLOW wins.")
                                        break
                                    if board_full(confirmed_board):
                                        print("\nBoard is full. Draw.")
                                        break

                                    ai_move_col, ai_expected_board, score = compute_ai_move_with_animation(
                                        confirmed_board,
                                        args.depth,
                                    )
                                    if ai_move_col is None or ai_expected_board is None:
                                        print("\nNo legal AI move found. Game over.")
                                        break

                                    print_ai_instruction(ai_move_col, score, ai_expected_board)
                                    input("Place the RED piece there, then press Enter to continue...")
                                    confirmed_board = accept_confirmed_ai_move(confirmed_board, ai_expected_board)
                                    sync_tracker_state(tracker, confirmed_board)
                                    last_seen_board = np.copy(confirmed_board)
                                    stable_board = np.copy(confirmed_board)
                                    stable_streak = args.state_streak
                                    if board_winner(confirmed_board) == AI_PIECE:
                                        print("\nRED wins.")
                                        break
                                    if board_full(confirmed_board):
                                        print("\nBoard is full. Draw.")
                                        break
                                    illegal_notice = None
                                    ai_illegal_retries = 0
                                    last_rejected_ai_board = None
                                    last_ai_inference_key = None
                                    ai_inference_hold = 0
                                    stable_printed_board = None
                                    game_state = "waiting_human"
                                    waiting_ai_notice = False

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
