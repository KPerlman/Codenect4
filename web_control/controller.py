import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from FullSubsystems.game_state_cv import (
    boards_equal,
    board_full,
    board_winner,
    choose_camera,
    compute_ai_move,
    find_single_added_piece,
    internal_column_from_user,
    legal_human_transition,
    open_first_available_camera,
    reopen_camera,
    user_visible_column,
    warmup_camera,
)
from connect4_vision import Connect4Tracker


ROOT_DIR = Path(__file__).resolve().parents[1]


def board_to_lists(board_state):
    if board_state is None:
        return None
    return np.asarray(board_state, dtype=int).tolist()


@dataclass
class SharedState:
    game_running: bool = False
    game_status: str = "idle"
    sorting_enabled: bool = False
    sorter_running: bool = False
    current_board: list[list[int]] = field(default_factory=lambda: [[0] * 7 for _ in range(6)])
    confirmed_board: list[list[int]] = field(default_factory=lambda: [[0] * 7 for _ in range(6)])
    suggested_red_column: int | None = None
    detected_yellow_column: int | None = None
    awaiting_confirmation: str | None = None
    prompt: str | None = None
    message: str = "Idle"
    error: str | None = None
    winner: int = 0
    tracker_active: bool = False
    tracker_calibrated: bool = False
    camera_source: str | None = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "game_running": self.game_running,
            "game_status": self.game_status,
            "sorting_enabled": self.sorting_enabled,
            "sorter_running": self.sorter_running,
            "current_board": self.current_board,
            "confirmed_board": self.confirmed_board,
            "suggested_red_column": self.suggested_red_column,
            "detected_yellow_column": self.detected_yellow_column,
            "awaiting_confirmation": self.awaiting_confirmation,
            "prompt": self.prompt,
            "message": self.message,
            "error": self.error,
            "winner": self.winner,
            "tracker_active": self.tracker_active,
            "tracker_calibrated": self.tracker_calibrated,
            "camera_source": self.camera_source,
            "updated_at": self.updated_at,
        }


class RobotWebController:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = SharedState()
        self._game_thread = None
        self._game_stop_event = None
        self._game_commands = None
        self._sorter_process = None

    def get_state(self):
        with self._lock:
            return self._state.to_dict()

    def _update_state(self, **changes):
        with self._lock:
            for key, value in changes.items():
                setattr(self._state, key, value)
            self._state.updated_at = time.time()

    def start_game(self, camera=None, device=None, width=640, height=480, depth=5, state_streak=3):
        with self._lock:
            if self._game_thread and self._game_thread.is_alive():
                return self._state.to_dict()
            self._game_stop_event = threading.Event()
            self._game_commands = queue.Queue()
            worker = GameLoopWorker(
                controller=self,
                stop_event=self._game_stop_event,
                commands=self._game_commands,
                camera=camera,
                device=device,
                width=width,
                height=height,
                depth=depth,
                state_streak=state_streak,
            )
            self._game_thread = threading.Thread(target=worker.run, daemon=True, name="game-loop-worker")
            self._game_thread.start()
            self._update_state(
                game_running=True,
                game_status="starting",
                message="Starting game loop",
                error=None,
            )
            return self._state.to_dict()

    def stop_game(self):
        thread = None
        with self._lock:
            if self._game_stop_event is not None:
                self._game_stop_event.set()
            if self._game_commands is not None:
                self._game_commands.put({"type": "stop"})
            thread = self._game_thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        self._update_state(
            game_running=False,
            game_status="stopped",
            awaiting_confirmation=None,
            prompt=None,
            suggested_red_column=None,
            detected_yellow_column=None,
            message="Game loop stopped",
        )
        return self.get_state()

    def reset_game(self, camera=None, device=None, width=640, height=480, depth=5, state_streak=3):
        self.stop_game()
        time.sleep(0.2)
        return self.start_game(camera=camera, device=device, width=width, height=height, depth=depth, state_streak=state_streak)

    def enable_sorting(self):
        with self._lock:
            if self._sorter_process and self._sorter_process.poll() is None:
                self._update_state(sorting_enabled=True, sorter_running=True, message="Sorter already running")
                return self._state.to_dict()

        cmd = [sys.executable, str(ROOT_DIR / "FullSubsystems" / "sorter.py")]
        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._sorter_process = process
        self._update_state(sorting_enabled=True, sorter_running=True, message="Sorter enabled")
        return self.get_state()

    def disable_sorting(self):
        with self._lock:
            process = self._sorter_process
            self._sorter_process = None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
        self._update_state(sorting_enabled=False, sorter_running=False, message="Sorter disabled")
        return self.get_state()

    def confirm_yellow(self, accept=True, column=None):
        if self._game_commands is None:
            return self.get_state()
        self._game_commands.put({"type": "confirm_yellow", "accept": accept, "column": column})
        return self.get_state()

    def confirm_red(self):
        if self._game_commands is None:
            return self.get_state()
        self._game_commands.put({"type": "confirm_red"})
        return self.get_state()

    def manual_human_move(self, column):
        if self._game_commands is None:
            return self.get_state()
        self._game_commands.put({"type": "manual_human_move", "column": column})
        return self.get_state()

    def _finalize_game_stop(self, message, error=None):
        self._update_state(
            game_running=False,
            game_status="stopped" if error is None else "error",
            awaiting_confirmation=None,
            prompt=None,
            suggested_red_column=None,
            detected_yellow_column=None,
            message=message,
            error=error,
        )


class GameLoopWorker:
    def __init__(self, controller, stop_event, commands, camera, device, width, height, depth, state_streak):
        self.controller = controller
        self.stop_event = stop_event
        self.commands = commands
        self.camera = camera
        self.device = device
        self.width = width
        self.height = height
        self.depth = depth
        self.state_streak = state_streak

    def _sync_tracker_board(self, tracker, board_state):
        tracker.board_state = np.copy(board_state)
        board_list = board_to_lists(board_state)
        self.controller._update_state(
            current_board=board_list,
            confirmed_board=board_list,
            winner=board_winner(board_state),
        )

    def _drain_commands(self):
        commands = []
        while True:
            try:
                commands.append(self.commands.get_nowait())
            except queue.Empty:
                return commands

    def _handle_manual_move(self, confirmed_board, visible_column):
        internal_column = internal_column_from_user(np.asarray(confirmed_board), visible_column)
        next_board = np.copy(confirmed_board)
        for row in range(next_board.shape[0] - 1, -1, -1):
            if next_board[row, internal_column] == 0:
                next_board[row, internal_column] = 2
                return next_board
        return None

    def _await_yellow_confirmation(self, pending_board, pending_visible_col):
        self.controller._update_state(
            game_status="awaiting_yellow_confirmation",
            awaiting_confirmation="yellow",
            detected_yellow_column=pending_visible_col,
            prompt=(
                f"Detected YELLOW in column {pending_visible_col}. "
                "Confirm it or enter the correct column in the app."
            ),
            message="Waiting for YELLOW confirmation",
        )
        while not self.stop_event.is_set():
            for command in self._drain_commands():
                if command["type"] == "stop":
                    return None
                if command["type"] == "confirm_yellow":
                    accept = command.get("accept", True)
                    if accept:
                        return np.copy(pending_board)
                    column = command.get("column")
                    if column is None:
                        continue
                    corrected = self._handle_manual_move(self.confirmed_board, column)
                    if corrected is not None:
                        return corrected
                if command["type"] == "manual_human_move":
                    corrected = self._handle_manual_move(self.confirmed_board, command["column"])
                    if corrected is not None:
                        return corrected
            time.sleep(0.1)
        return None

    def _await_red_confirmation(self, ai_expected_board, ai_visible_column):
        self.controller._update_state(
            game_status="awaiting_red_confirmation",
            awaiting_confirmation="red",
            suggested_red_column=ai_visible_column,
            prompt=f"Place RED in column {ai_visible_column}, then confirm in the app.",
            message="Waiting for RED placement confirmation",
        )
        while not self.stop_event.is_set():
            for command in self._drain_commands():
                if command["type"] == "stop":
                    return None
                if command["type"] == "confirm_red":
                    return np.copy(ai_expected_board)
            time.sleep(0.1)
        return None

    def run(self):
        cap = None
        tracker = Connect4Tracker()
        remaining_candidates = []
        camera_source = None
        failed_reads = 0
        confirmed_board = None
        last_seen_board = None
        stable_streak = 0
        stable_board = None

        try:
            candidates = choose_camera(
                preferred_index=self.camera,
                preferred_device=self.device,
                width=self.width,
                height=self.height,
            )
            cap, camera_source = open_first_available_camera(candidates, self.width, self.height)
            warmup_camera(cap)
            remaining_candidates = [source for source in candidates if source != camera_source]
            self.controller._update_state(
                camera_source=str(camera_source),
                game_running=True,
                game_status="calibrating",
                message="Waiting for camera and tracker calibration",
                error=None,
            )

            while not self.stop_event.is_set():
                for command in self._drain_commands():
                    if command["type"] == "stop":
                        self.stop_event.set()
                        break
                if self.stop_event.is_set():
                    break

                ret, frame = cap.read()
                if not ret:
                    failed_reads += 1
                    if failed_reads < 5:
                        time.sleep(0.1)
                        continue

                    self.controller._update_state(message=f"Camera read failed; reopening {camera_source}")
                    cap.release()
                    reopened = reopen_camera(camera_source, self.width, self.height, attempts=12, delay_s=0.5)
                    if reopened is not None:
                        cap = reopened
                        failed_reads = 0
                        warmup_camera(cap)
                        continue

                    if remaining_candidates:
                        cap, camera_source = open_first_available_camera(remaining_candidates, self.width, self.height)
                        remaining_candidates = [source for source in remaining_candidates if source != camera_source]
                        tracker = Connect4Tracker()
                        confirmed_board = None
                        last_seen_board = None
                        stable_streak = 0
                        stable_board = None
                        failed_reads = 0
                        warmup_camera(cap)
                        self.controller._update_state(camera_source=str(camera_source), game_status="calibrating")
                        continue

                    raise RuntimeError("Camera frame read failed and no camera recovered.")

                failed_reads = 0
                _, _, _ = tracker.process_frame(frame)
                board_copy = np.copy(tracker.board_state)

                if boards_equal(board_copy, last_seen_board):
                    stable_streak += 1
                else:
                    last_seen_board = np.copy(board_copy)
                    stable_streak = 1

                if stable_streak >= self.state_streak:
                    stable_board = np.copy(board_copy)

                self.controller._update_state(
                    tracker_active=tracker.is_board_active,
                    tracker_calibrated=tracker.is_calibrated,
                    current_board=board_to_lists(board_copy),
                    winner=tracker.winner,
                )

                if not tracker.is_calibrated:
                    self.controller._update_state(game_status="calibrating", message="Calibrating empty board")
                    continue
                if stable_board is None:
                    continue

                if confirmed_board is None:
                    confirmed_board = np.copy(stable_board)
                    self.confirmed_board = confirmed_board
                    self._sync_tracker_board(tracker, confirmed_board)
                    self.controller._update_state(
                        game_status="waiting_human_move",
                        awaiting_confirmation=None,
                        prompt="Drop a YELLOW piece, or enter its column in the app.",
                        message="Waiting for YELLOW move",
                    )
                    continue

                self.confirmed_board = confirmed_board

                manual_applied = False
                for command in self._drain_commands():
                    if command["type"] == "manual_human_move":
                        manual_board = self._handle_manual_move(confirmed_board, command["column"])
                        if manual_board is not None:
                            confirmed_board = manual_board
                            self.confirmed_board = confirmed_board
                            self._sync_tracker_board(tracker, confirmed_board)
                            stable_board = np.copy(confirmed_board)
                            last_seen_board = np.copy(confirmed_board)
                            stable_streak = self.state_streak
                            manual_applied = True
                            break
                    elif command["type"] == "stop":
                        self.stop_event.set()
                        break
                if self.stop_event.is_set():
                    break

                if manual_applied:
                    pass
                else:
                    is_legal, _ = legal_human_transition(confirmed_board, stable_board)
                    if not is_legal:
                        continue
                    added = find_single_added_piece(confirmed_board, stable_board, 2)
                    if added is None:
                        continue
                    _, internal_col = added
                    visible_col = user_visible_column(stable_board, internal_col)
                    maybe_board = self._await_yellow_confirmation(stable_board, visible_col)
                    if maybe_board is None:
                        break
                    confirmed_board = np.copy(maybe_board)
                    self.confirmed_board = confirmed_board
                    self._sync_tracker_board(tracker, confirmed_board)

                if board_winner(confirmed_board) == 2:
                    self.controller._update_state(
                        game_status="finished",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="YELLOW wins",
                        winner=2,
                    )
                    break
                if board_full(confirmed_board):
                    self.controller._update_state(
                        game_status="finished",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="Board full: draw",
                    )
                    break

                self.controller._update_state(
                    game_status="thinking",
                    awaiting_confirmation=None,
                    suggested_red_column=None,
                    prompt="Thinking about RED placement...",
                    message="Thinking",
                )
                ai_move_col, ai_expected_board, score = compute_ai_move(confirmed_board, self.depth)
                if ai_move_col is None or ai_expected_board is None:
                    self.controller._update_state(game_status="finished", message="No legal RED move found")
                    break

                visible_red_col = user_visible_column(ai_expected_board, ai_move_col)
                self.controller._update_state(
                    suggested_red_column=visible_red_col,
                    message=f"Computer chose RED column {visible_red_col} (score={score})",
                )
                maybe_red_board = self._await_red_confirmation(ai_expected_board, visible_red_col)
                if maybe_red_board is None:
                    break
                confirmed_board = np.copy(maybe_red_board)
                self.confirmed_board = confirmed_board
                self._sync_tracker_board(tracker, confirmed_board)
                stable_board = np.copy(confirmed_board)
                last_seen_board = np.copy(confirmed_board)
                stable_streak = self.state_streak

                if board_winner(confirmed_board) == 1:
                    self.controller._update_state(
                        game_status="finished",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="RED wins",
                        winner=1,
                    )
                    break
                if board_full(confirmed_board):
                    self.controller._update_state(
                        game_status="finished",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="Board full: draw",
                    )
                    break

                self.controller._update_state(
                    game_status="waiting_human_move",
                    awaiting_confirmation=None,
                    detected_yellow_column=None,
                    suggested_red_column=None,
                    prompt="Drop a YELLOW piece, or enter its column in the app.",
                    message="Waiting for YELLOW move",
                )

            if self.stop_event.is_set():
                self.controller._finalize_game_stop("Game loop stopped")
        except Exception as exc:
            self.controller._finalize_game_stop("Game loop failed", error=str(exc))
        finally:
            if cap is not None:
                cap.release()
