import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from servo_config import SERVO_MAX_ANGLES, SERVO_OFFSETS

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
def move_servo_zero_position(pca, channel, angle, max_angle=180, offset=0):
    pulse_min = 450
    pulse_max = 2550
    corrected_angle = max(0, min(max_angle, angle + offset))
    pulse = pulse_min + (corrected_angle / float(max_angle)) * (pulse_max - pulse_min)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def board_to_lists(board_state):
    if board_state is None:
        return None
    return np.asarray(board_state, dtype=int).tolist()


@dataclass
class SharedState:
    game_running: bool = False
    game_status: str = "idle"
    game_phase: str = "idle"
    turn_state: str = "idle"
    sorting_enabled: bool = False
    sorter_running: bool = False
    current_board: list[list[int]] = field(default_factory=lambda: [[0] * 7 for _ in range(6)])
    confirmed_board: list[list[int]] = field(default_factory=lambda: [[0] * 7 for _ in range(6)])
    suggested_red_column: int | None = None
    detected_yellow_column: int | None = None
    confirmed_red_count: int = 0
    confirmed_yellow_count: int = 0
    pending_yellow_count: int = 0
    awaiting_confirmation: str | None = None
    prompt: str | None = None
    message: str = "Idle"
    error: str | None = None
    winner: int = 0
    tracker_active: bool = False
    tracker_calibrated: bool = False
    camera_source: str | None = None
    sorter_calibration_running: bool = False
    sorter_calibration_prompt: str | None = None
    sorter_calibration_sample: dict[str, float] | None = None
    sorter_calibration_counts: dict[str, int] = field(
        default_factory=lambda: {"red": 0, "yellow": 0, "none": 0}
    )
    sorter_calibration_values: dict[str, float] | None = None
    belt_running: bool = False
    belt_status: str = "idle"
    belt_mode: str = "continuous"
    belt_speed: int = 600
    belt_accel: int = 400
    belt_steps: int | None = None
    belt_error: str | None = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "game_running": self.game_running,
            "game_status": self.game_status,
            "game_phase": self.game_phase,
            "turn_state": self.turn_state,
            "sorting_enabled": self.sorting_enabled,
            "sorter_running": self.sorter_running,
            "current_board": self.current_board,
            "confirmed_board": self.confirmed_board,
            "suggested_red_column": self.suggested_red_column,
            "detected_yellow_column": self.detected_yellow_column,
            "confirmed_red_count": self.confirmed_red_count,
            "confirmed_yellow_count": self.confirmed_yellow_count,
            "pending_yellow_count": self.pending_yellow_count,
            "awaiting_confirmation": self.awaiting_confirmation,
            "prompt": self.prompt,
            "message": self.message,
            "error": self.error,
            "winner": self.winner,
            "tracker_active": self.tracker_active,
            "tracker_calibrated": self.tracker_calibrated,
            "camera_source": self.camera_source,
            "sorter_calibration_running": self.sorter_calibration_running,
            "sorter_calibration_prompt": self.sorter_calibration_prompt,
            "sorter_calibration_sample": self.sorter_calibration_sample,
            "sorter_calibration_counts": self.sorter_calibration_counts,
            "sorter_calibration_values": self.sorter_calibration_values,
            "belt_running": self.belt_running,
            "belt_status": self.belt_status,
            "belt_mode": self.belt_mode,
            "belt_speed": self.belt_speed,
            "belt_accel": self.belt_accel,
            "belt_steps": self.belt_steps,
            "belt_error": self.belt_error,
            "updated_at": self.updated_at,
        }


class RobotWebController:
    def __init__(self):
        self._lock = threading.RLock()
        self._state = SharedState()
        self._game_thread = None
        self._game_stop_event = None
        self._game_commands = None
        self._sorter_process = None
        self._sorter_runtime_args = []
        self._sorter_calibration_thread = None
        self._sorter_calibration_stop_event = None
        self._sorter_calibration_commands = None
        self._belt_thread = None
        self._belt_stop_event = None

    def start_belt(self, speed=600, accel=400, steps=None):
        with self._lock:
            if self._belt_thread and self._belt_thread.is_alive():
                return self._state.to_dict()
            self._belt_stop_event = threading.Event()
            worker = BeltWorker(
                controller=self,
                stop_event=self._belt_stop_event,
                speed=speed,
                accel=accel,
                steps=steps,
            )
            self._belt_thread = threading.Thread(
                target=worker.run,
                daemon=True,
                name="belt-worker",
            )
            self._belt_thread.start()
            self._update_state(
                belt_running=True,
                belt_status="starting",
                belt_mode="steps" if steps is not None else "continuous",
                belt_speed=speed,
                belt_accel=accel,
                belt_steps=steps,
                belt_error=None,
                message="Starting belt",
            )
            return self._state.to_dict()

    def stop_belt(self):
        thread = None
        with self._lock:
            if self._belt_stop_event is not None:
                self._belt_stop_event.set()
            thread = self._belt_thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        self._update_state(
            belt_running=False,
            belt_status="stopped",
            message="Belt stopped",
        )
        return self.get_state()

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
            calibration_running = (
                self._sorter_calibration_thread is not None
                and self._sorter_calibration_thread.is_alive()
            )
            runtime_args = list(self._sorter_runtime_args)
        if calibration_running:
            self._update_state(message="Sorter calibration is running", error=None)
            return self.get_state()

        with self._lock:
            if self._sorter_process and self._sorter_process.poll() is None:
                self._update_state(sorting_enabled=True, sorter_running=True, message="Sorter already running")
                return self._state.to_dict()

        cmd = [sys.executable, str(ROOT_DIR / "FullSubsystems" / "sorter.py"), *runtime_args]
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

    def start_sorter_calibration(self, sensor_bus=3):
        self.disable_sorting()
        with self._lock:
            if self._sorter_calibration_thread and self._sorter_calibration_thread.is_alive():
                return self._state.to_dict()
            self._sorter_calibration_stop_event = threading.Event()
            self._sorter_calibration_commands = queue.Queue()
            worker = SorterCalibrationWorker(
                controller=self,
                stop_event=self._sorter_calibration_stop_event,
                commands=self._sorter_calibration_commands,
                sensor_bus=sensor_bus,
            )
            self._sorter_calibration_thread = threading.Thread(
                target=worker.run,
                daemon=True,
                name="sorter-calibration-worker",
            )
            self._sorter_calibration_thread.start()
            self._update_state(
                sorter_calibration_running=True,
                sorter_calibration_prompt="Starting sorter calibration",
                sorter_calibration_sample=None,
                sorter_calibration_counts={"red": 0, "yellow": 0, "none": 0},
                message="Starting sorter calibration",
                error=None,
                sorter_running=False,
                sorting_enabled=False,
            )
            return self._state.to_dict()

    def submit_sorter_calibration_label(self, label):
        if self._sorter_calibration_commands is None:
            return self.get_state()
        self._sorter_calibration_commands.put({"type": "label", "label": label})
        return self.get_state()

    def zero_servos(self):
        try:
            import board
            import busio
            from adafruit_pca9685 import PCA9685

            i2c = busio.I2C(board.SCL, board.SDA)
            pca = PCA9685(i2c)
            pca.frequency = 50
            try:
                for channel in range(7):
                    move_servo_zero_position(
                        pca,
                        channel,
                        45,
                        max_angle=SERVO_MAX_ANGLES[channel],
                        offset=SERVO_OFFSETS[channel],
                    )
                time.sleep(0.5)

                for channel in range(7):
                    move_servo_zero_position(
                        pca,
                        channel,
                        0,
                        max_angle=SERVO_MAX_ANGLES[channel],
                        offset=SERVO_OFFSETS[channel],
                    )
                time.sleep(0.85)
            finally:
                pca.deinit()
            self._update_state(message="All servos swept to 45 and returned to zero", error=None)
        except Exception as exc:
            self._update_state(
                error=f"Failed to zero servos: {exc}",
                message="Servo zero command failed",
            )
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
        confirmed_red = int(np.count_nonzero(board_state == 1))
        confirmed_yellow = int(np.count_nonzero(board_state == 2))
        self.controller._update_state(
            current_board=board_list,
            confirmed_board=board_list,
            winner=board_winner(board_state),
            confirmed_red_count=confirmed_red,
            confirmed_yellow_count=confirmed_yellow,
            pending_yellow_count=0,
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
        pending_yellow_count = int(np.count_nonzero(pending_board == 2)) - int(
            np.count_nonzero(np.asarray(self.confirmed_board) == 2)
        )
        self.controller._update_state(
            game_status="awaiting_yellow_confirmation",
            game_phase="human_confirmation",
            turn_state="human_pending_confirmation",
            awaiting_confirmation="yellow",
            detected_yellow_column=pending_visible_col,
            pending_yellow_count=max(0, pending_yellow_count),
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
            game_phase="robot_confirmation",
            turn_state="robot_waiting_for_placement",
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
        recovery_cycles = 0
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
                game_phase="calibrating",
                turn_state="booting",
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

                    recovery_cycles += 1
                    if recovery_cycles > 3:
                        raise RuntimeError(
                            f"Camera repeatedly failed to recover on {camera_source}. "
                            "Check the USB camera connection and restart the game loop."
                        )

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
                recovery_cycles = 0
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
                    pending_yellow_count=max(
                        0,
                        int(np.count_nonzero(board_copy == 2))
                        - int(np.count_nonzero(np.asarray(confirmed_board) == 2)) if confirmed_board is not None else 0,
                    ),
                )

                if not tracker.is_calibrated:
                    self.controller._update_state(
                        game_status="calibrating",
                        game_phase="calibrating",
                        turn_state="booting",
                        message="Calibrating empty board",
                    )
                    continue
                if stable_board is None:
                    continue

                if confirmed_board is None:
                    confirmed_board = np.copy(stable_board)
                    self.confirmed_board = confirmed_board
                    self._sync_tracker_board(tracker, confirmed_board)
                    self.controller._update_state(
                        game_status="waiting_human_move",
                        game_phase="live",
                        turn_state="human_turn",
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
                            self.controller._update_state(
                                game_phase="live",
                                turn_state="human_move_registered",
                                message=f"Manual YELLOW move recorded in column {command['column']}",
                            )
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
                        game_phase="complete",
                        turn_state="game_over",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="YELLOW wins",
                        winner=2,
                    )
                    break
                if board_full(confirmed_board):
                    self.controller._update_state(
                        game_status="finished",
                        game_phase="complete",
                        turn_state="game_over",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="Board full: draw",
                    )
                    break

                self.controller._update_state(
                    game_status="thinking",
                    game_phase="live",
                    turn_state="robot_thinking",
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
                        game_phase="complete",
                        turn_state="game_over",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="RED wins",
                        winner=1,
                    )
                    break
                if board_full(confirmed_board):
                    self.controller._update_state(
                        game_status="finished",
                        game_phase="complete",
                        turn_state="game_over",
                        awaiting_confirmation=None,
                        prompt=None,
                        message="Board full: draw",
                    )
                    break

                self.controller._update_state(
                    game_status="waiting_human_move",
                    game_phase="live",
                    turn_state="human_turn",
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


class SorterCalibrationWorker:
    def __init__(self, controller, stop_event, commands, sensor_bus):
        self.controller = controller
        self.stop_event = stop_event
        self.commands = commands
        self.sensor_bus = sensor_bus

    def _wait_for_label(self):
        while not self.stop_event.is_set():
            try:
                command = self.commands.get(timeout=0.1)
            except queue.Empty:
                continue
            if command["type"] == "label":
                return command["label"]
        return "q"

    def run(self):
        pca = None
        try:
            import board
            import busio
            from adafruit_pca9685 import PCA9685

            from FullSubsystems.sorter import (
                DETECT,
                DETECT_SETTLE,
                DROP_HOLD,
                DROP_SETTLE,
                LEFT_PICKUP,
                MAX_ANGLE,
                OFFSET,
                PICKUP_SETTLE,
                PLAYER_DROP,
                RIGHT_PICKUP,
                ROBOT_DROP,
                SERVO_CHANNEL,
                YELLOW_CLEAR,
                YELLOW_GREEN_MIN,
                YELLOW_RG_RATIO,
                CLEAR_THRESH,
                RED_MARGIN,
                build_sorter_runtime_args,
                compute_calibration_results,
                format_sorter_run_command,
                move_servo,
                read_sample,
            )
            from tcs_bus import open_tcs34725

            i2c_pca = busio.I2C(board.SCL, board.SDA)
            pca = PCA9685(i2c_pca)
            pca.frequency = 50
            sensor = open_tcs34725(self.sensor_bus, integration_time_ms=100, gain=4)

            red_samples = []
            yellow_samples = []
            none_samples = []
            next_pickup_right = True

            move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
            time.sleep(1.0)

            while not self.stop_event.is_set():
                pickup_angle = RIGHT_PICKUP if next_pickup_right else LEFT_PICKUP
                next_pickup_right = not next_pickup_right

                move_servo(pca, SERVO_CHANNEL, pickup_angle, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(PICKUP_SETTLE)

                move_servo(pca, SERVO_CHANNEL, DETECT, max_angle=MAX_ANGLE, offset=OFFSET)
                time.sleep(DETECT_SETTLE)

                r, g, b, clear = read_sample(sensor)
                sample = {"r": r, "g": g, "b": b, "clear": clear}
                counts = {
                    "red": len(red_samples),
                    "yellow": len(yellow_samples),
                    "none": len(none_samples),
                }
                self.controller._update_state(
                    sorter_calibration_running=True,
                    sorter_calibration_prompt=(
                        "Label the current piece as red, yellow, none, or finish calibration."
                    ),
                    sorter_calibration_sample=sample,
                    sorter_calibration_counts=counts,
                    message="Sorter calibration awaiting label",
                    error=None,
                )

                label = self._wait_for_label()
                if label == "q":
                    break
                if label not in {"r", "y", "n"}:
                    continue

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
                    move_servo(pca, SERVO_CHANNEL, pickup_angle, max_angle=MAX_ANGLE, offset=OFFSET)
                    time.sleep(DROP_SETTLE)
                    time.sleep(DROP_HOLD)

            results = compute_calibration_results(
                red_samples,
                yellow_samples,
                none_samples,
                CLEAR_THRESH,
                RED_MARGIN,
                YELLOW_CLEAR,
                YELLOW_GREEN_MIN,
                YELLOW_RG_RATIO,
            )
            runtime_args = build_sorter_runtime_args(self.sensor_bus, results)
            counts = {
                "red": len(red_samples),
                "yellow": len(yellow_samples),
                "none": len(none_samples),
            }

            with self.controller._lock:
                self.controller._sorter_runtime_args = runtime_args

            self.controller._update_state(
                sorter_calibration_running=False,
                sorter_calibration_prompt="Calibration complete. Future sorting runs will use these calibration values.",
                sorter_calibration_sample=None,
                sorter_calibration_counts=counts,
                sorter_calibration_values={
                    "clear_thresh": results["clear_thresh"],
                    "red_margin": results["red_margin"],
                    "yellow_clear": results["yellow_clear"],
                    "yellow_green_min": results["yellow_green_min"],
                    "yellow_rg_ratio": results["yellow_rg_ratio"],
                },
                message=(
                    "Sorter calibration complete. "
                    + format_sorter_run_command(self.sensor_bus, results, debug=False)
                ),
                error=None,
                sorting_enabled=False,
                sorter_running=False,
            )
            with self.controller._lock:
                self.controller._sorter_calibration_thread = None
        except Exception as exc:
            self.controller._update_state(
                sorter_calibration_running=False,
                sorter_calibration_prompt=f"Calibration failed: {exc}",
                sorter_calibration_sample=None,
                message="Sorter calibration failed",
                error=str(exc),
            )
        finally:
            with self.controller._lock:
                if self.controller._sorter_calibration_thread is threading.current_thread():
                    self.controller._sorter_calibration_thread = None
            if pca is not None:
                try:
                    from FullSubsystems.sorter import MAX_ANGLE, OFFSET, PLAYER_DROP, SERVO_CHANNEL, move_servo

                    move_servo(pca, SERVO_CHANNEL, PLAYER_DROP, max_angle=MAX_ANGLE, offset=OFFSET)
                except Exception:
                    pass
                pca.deinit()


class BeltWorker:
    PORT = "/dev/serial0"

    def __init__(self, controller, stop_event, speed, accel, steps):
        self.controller = controller
        self.stop_event = stop_event
        self.speed = speed
        self.accel = accel
        self.steps = steps

    def _wait_for(self, arduino, targets, timeout_s=5.0):
        deadline = time.time() + timeout_s
        while True:
            if self.stop_event.is_set():
                raise RuntimeError("Belt stop requested")
            if time.time() > deadline:
                raise TimeoutError(f"Timeout waiting for {targets}")
            line = arduino.readline().decode(errors="ignore").strip()
            line = "".join(ch for ch in line if ch.isprintable())
            if line in targets:
                return line

    def _send_and_wait(self, arduino, command, targets, timeout_s=5.0, attempts=3, pre_delay_s=0.1):
        last_error = None
        for _ in range(attempts):
            time.sleep(pre_delay_s)
            arduino.write(f"{command}\n".encode())
            try:
                return self._wait_for(arduino, targets, timeout_s=timeout_s)
            except TimeoutError as exc:
                last_error = exc
                arduino.reset_input_buffer()
                time.sleep(0.2)
        raise last_error

    def _sync_controller(self, arduino, attempts=6, timeout_s=1.5):
        for _ in range(attempts):
            arduino.write(b"PING\n")
            try:
                self._wait_for(arduino, {"PONG"}, timeout_s=timeout_s)
                time.sleep(0.3)
                arduino.reset_input_buffer()
                return
            except TimeoutError:
                arduino.reset_input_buffer()
                time.sleep(0.3)
        raise TimeoutError("Controller did not respond to PING")

    def run(self):
        arduino = None
        try:
            import serial

            arduino = serial.Serial(self.PORT, 9600, timeout=1)
            time.sleep(2)
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()

            self._sync_controller(arduino)
            self._send_and_wait(arduino, f"SPEED {self.speed}", {"OK", "ERR"})
            self._send_and_wait(arduino, f"ACCEL {self.accel}", {"OK", "ERR"})

            if self.steps is not None:
                self.controller._update_state(
                    belt_status="running",
                    belt_mode="steps",
                    message=f"Running belt for {self.steps} steps",
                )
                self._send_and_wait(arduino, f"STEPS {self.steps}", {"DONE"}, timeout_s=10.0)
                self.controller._update_state(
                    belt_running=False,
                    belt_status="completed",
                    message=f"Belt step run completed ({self.steps} steps)",
                )
            else:
                self._send_and_wait(arduino, f"RUN {self.speed}", {"OK", "ERR"})
                self.controller._update_state(
                    belt_running=True,
                    belt_status="running",
                    belt_mode="continuous",
                    message=f"Belt running continuously at {self.speed} steps/sec",
                )
                while not self.stop_event.is_set():
                    time.sleep(0.1)
                self._send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0)
                self.controller._update_state(
                    belt_running=False,
                    belt_status="stopped",
                    message="Belt stopped",
                )
        except Exception as exc:
            self.controller._update_state(
                belt_running=False,
                belt_status="error",
                belt_error=str(exc),
                message="Belt control failed",
                error=str(exc),
            )
        finally:
            with self.controller._lock:
                if self.controller._belt_thread is threading.current_thread():
                    self.controller._belt_thread = None
            if arduino is not None:
                try:
                    arduino.close()
                except Exception:
                    pass
