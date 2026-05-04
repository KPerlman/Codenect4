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
    legal_ai_transition,
    legal_human_transition,
    open_first_available_camera,
    reopen_camera,
    user_visible_column,
    warmup_camera,
)
from connect4_vision import Connect4Tracker


ROOT_DIR = Path(__file__).resolve().parents[1]
DROP_SERVO_ANGLE = 100
GATE_PORT = "/dev/serial0"
GATE_DEFAULT_SPEED = 600
GATE_DEFAULT_ACCEL = 400
GATE_DEFAULT_STEPS = 1000
BELT_CLEAR_THRESH = 185.0
BELT_POST_DETECT_DELAY_MS = 500
BELT_STAGE_SPEED = 500
BELT_LAUNCH_SPEED = 4000
BELT_LAUNCH_ACCEL = 400
BELT_LAUNCH_STEPS = 2000
BELT_DETECT_INTEGRATION_MS = 12
BELT_DETECT_SAMPLES = 1
BELT_DETECT_STREAK = 1
BELT_DETECT_SAMPLE_DELAY_S = 0.005
RUNTIME_LOG_LIMIT = 200


def move_servo_zero_position(pca, channel, angle, max_angle=180, offset=0):
    pulse_min = 450
    pulse_max = 2550
    corrected_angle = max(0, min(max_angle, angle + offset))
    pulse = pulse_min + (corrected_angle / float(max_angle)) * (pulse_max - pulse_min)
    pca.channels[channel].duty_cycle = int(pulse / 20000 * 65535)


def move_game_servo(pca, channel, angle):
    move_servo_zero_position(
        pca,
        channel,
        angle,
        max_angle=SERVO_MAX_ANGLES[channel],
        offset=SERVO_OFFSETS[channel],
    )


def drop_servo_channel_for_visible_column(visible_column):
    if visible_column is None or visible_column <= 0:
        return None
    if visible_column > 6:
        return None
    return 6 - visible_column


def board_to_lists(board_state):
    if board_state is None:
        return None
    return np.asarray(board_state, dtype=int).tolist()


@dataclass
class SharedState:
    game_running: bool = False
    game_paused: bool = False
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
    game_belt_enabled: bool = True
    belt_speed: int = 600
    belt_accel: int = 400
    belt_steps: int | None = None
    belt_launch_speed: int = BELT_LAUNCH_SPEED
    belt_launch_accel: int = BELT_LAUNCH_ACCEL
    belt_launch_steps: int = BELT_LAUNCH_STEPS
    belt_error: str | None = None
    belt_clear_thresh: float = BELT_CLEAR_THRESH
    belt_detect_mode: str = "below"
    belt_post_detect_delay_ms: int = BELT_POST_DETECT_DELAY_MS
    belt_detect_integration_ms: int = BELT_DETECT_INTEGRATION_MS
    belt_detect_samples: int = BELT_DETECT_SAMPLES
    belt_detect_streak: int = BELT_DETECT_STREAK
    belt_calibration_running: bool = False
    belt_calibration_prompt: str | None = None
    belt_calibration_last_sample: dict[str, float] | None = None
    belt_calibration_counts: dict[str, int] = field(
        default_factory=lambda: {"empty": 0, "piece": 0}
    )
    belt_test_running: bool = False
    belt_test_waiting_continue: bool = False
    belt_test_prompt: str | None = None
    belt_piece_ready: bool = False
    belt_ready_confirmed: bool = False
    gate_running: bool = False
    gate_status: str = "idle"
    gate_mode: str = "steps"
    gate_speed: int = GATE_DEFAULT_SPEED
    gate_accel: int = GATE_DEFAULT_ACCEL
    gate_steps: int | None = None
    gate_error: str | None = None
    runtime_log: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "game_running": self.game_running,
            "game_paused": self.game_paused,
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
            "game_belt_enabled": self.game_belt_enabled,
            "belt_speed": self.belt_speed,
            "belt_accel": self.belt_accel,
            "belt_steps": self.belt_steps,
            "belt_launch_speed": self.belt_launch_speed,
            "belt_launch_accel": self.belt_launch_accel,
            "belt_launch_steps": self.belt_launch_steps,
            "belt_error": self.belt_error,
            "belt_clear_thresh": self.belt_clear_thresh,
            "belt_detect_mode": self.belt_detect_mode,
            "belt_post_detect_delay_ms": self.belt_post_detect_delay_ms,
            "belt_detect_integration_ms": self.belt_detect_integration_ms,
            "belt_detect_samples": self.belt_detect_samples,
            "belt_detect_streak": self.belt_detect_streak,
            "belt_calibration_running": self.belt_calibration_running,
            "belt_calibration_prompt": self.belt_calibration_prompt,
            "belt_calibration_last_sample": self.belt_calibration_last_sample,
            "belt_calibration_counts": self.belt_calibration_counts,
            "belt_test_running": self.belt_test_running,
            "belt_test_waiting_continue": self.belt_test_waiting_continue,
            "belt_test_prompt": self.belt_test_prompt,
            "belt_piece_ready": self.belt_piece_ready,
            "belt_ready_confirmed": self.belt_ready_confirmed,
            "gate_running": self.gate_running,
            "gate_status": self.gate_status,
            "gate_mode": self.gate_mode,
            "gate_speed": self.gate_speed,
            "gate_accel": self.gate_accel,
            "gate_steps": self.gate_steps,
            "gate_error": self.gate_error,
            "updated_at": self.updated_at,
        }


class RobotWebController:
    def __init__(self):
        self._lock = threading.RLock()
        self._state = SharedState()
        self._arduino_lock = threading.Lock()
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
        self._belt_calibration_sensor = None
        self._belt_calibration_empty_samples = []
        self._belt_calibration_piece_samples = []
        self._belt_test_thread = None
        self._belt_test_stop_event = None
        self._belt_test_commands = None
        self._active_belt_feeder = None
        self._gate_thread = None
        self._gate_stop_event = None
        self._gate_is_out = False
        self._append_log_locked("Runtime controller initialized")

    def _append_log_locked(self, text):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {text}"
        self._state.runtime_log.append(entry)
        if len(self._state.runtime_log) > RUNTIME_LOG_LIMIT:
            self._state.runtime_log = self._state.runtime_log[-RUNTIME_LOG_LIMIT:]

    def log_event(self, text):
        with self._lock:
            self._append_log_locked(text)
            self._state.updated_at = time.time()

    def _log_state_changes_locked(self, previous_values, changes):
        field_labels = {
            "game_status": "Game status",
            "game_phase": "Game phase",
            "turn_state": "Turn state",
            "awaiting_confirmation": "Awaiting confirmation",
            "tracker_active": "Tracker active",
            "tracker_calibrated": "Tracker calibrated",
            "camera_source": "Camera source",
            "sorting_enabled": "Sorting enabled",
            "sorter_running": "Sorter running",
            "sorter_calibration_running": "Sorter calibration",
            "belt_running": "Belt running",
            "belt_status": "Belt status",
            "belt_mode": "Belt mode",
            "belt_piece_ready": "Belt piece ready",
            "belt_ready_confirmed": "Belt ready confirmed",
            "belt_test_running": "Belt test",
            "belt_calibration_running": "Belt calibration",
            "gate_running": "Gate running",
            "gate_status": "Gate status",
            "suggested_red_column": "Suggested red column",
            "detected_yellow_column": "Detected yellow column",
            "winner": "Winner",
        }

        for field_name, label in field_labels.items():
            if field_name in changes and previous_values.get(field_name) != changes[field_name]:
                self._append_log_locked(f"{label}: {changes[field_name]}")

        if "prompt" in changes and previous_values.get("prompt") != changes["prompt"] and changes["prompt"]:
            self._append_log_locked(f"Prompt: {changes['prompt']}")
        if "message" in changes and previous_values.get("message") != changes["message"] and changes["message"]:
            self._append_log_locked(f"Message: {changes['message']}")
        if "error" in changes and previous_values.get("error") != changes["error"]:
            if changes["error"]:
                self._append_log_locked(f"ERROR: {changes['error']}")
            elif previous_values.get("error"):
                self._append_log_locked("Error cleared")
        if "belt_error" in changes and previous_values.get("belt_error") != changes["belt_error"]:
            if changes["belt_error"]:
                self._append_log_locked(f"Belt error: {changes['belt_error']}")
            elif previous_values.get("belt_error"):
                self._append_log_locked("Belt error cleared")
        if "gate_error" in changes and previous_values.get("gate_error") != changes["gate_error"]:
            if changes["gate_error"]:
                self._append_log_locked(f"Gate error: {changes['gate_error']}")
            elif previous_values.get("gate_error"):
                self._append_log_locked("Gate error cleared")

    def _read_belt_color_sample(self, sensor, count=8, delay_s=0.04):
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

    def start_belt(self, speed=600, accel=400, steps=None):
        with self._lock:
            if self._belt_test_thread and self._belt_test_thread.is_alive():
                self._update_state(message="Stop belt calibration test before starting the belt")
                return self._state.to_dict()
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

    def set_belt_ready_confirmation(self, accept=True):
        with self._lock:
            if self._game_thread and self._game_thread.is_alive() and self._active_belt_feeder is not None:
                self._active_belt_feeder.confirm_ready(accept=accept)
                self._update_state(
                    belt_ready_confirmed=bool(accept),
                    message="Confirmed staged belt piece" if accept else "Rejected staged belt piece; resuming search",
                )
            elif self._game_thread and self._game_thread.is_alive():
                self._update_state(
                    message="No active staged belt piece is available to confirm",
                )
        return self.get_state()

    def start_belt_test(self):
        with self._lock:
            if self._game_thread and self._game_thread.is_alive():
                self._update_state(message="Pause or stop the game before testing belt calibration")
                return self._state.to_dict()
            if self._belt_thread and self._belt_thread.is_alive():
                self._update_state(message="Stop the belt before starting belt calibration test")
                return self._state.to_dict()
            if self._belt_test_thread and self._belt_test_thread.is_alive():
                return self._state.to_dict()
            self._belt_test_stop_event = threading.Event()
            self._belt_test_commands = queue.Queue()
            worker = BeltCalibrationTestWorker(
                controller=self,
                stop_event=self._belt_test_stop_event,
                commands=self._belt_test_commands,
            )
            self._belt_test_thread = threading.Thread(
                target=worker.run,
                daemon=True,
                name="belt-calibration-test-worker",
            )
            self._belt_test_thread.start()
            self._update_state(
                belt_test_running=True,
                belt_test_waiting_continue=False,
                belt_test_prompt="Starting belt calibration test.",
                belt_running=True,
                belt_status="test-starting",
                belt_error=None,
                message="Starting belt calibration test",
            )
            return self._state.to_dict()

    def continue_belt_test(self):
        with self._lock:
            if self._belt_test_commands is not None:
                self._belt_test_commands.put({"type": "continue"})
        return self.get_state()

    def stop_belt_test(self):
        thread = None
        with self._lock:
            if self._belt_test_stop_event is not None:
                self._belt_test_stop_event.set()
            if self._belt_test_commands is not None:
                self._belt_test_commands.put({"type": "stop"})
            thread = self._belt_test_thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        self._update_state(
            belt_test_running=False,
            belt_test_waiting_continue=False,
            belt_test_prompt="Belt calibration test stopped.",
            belt_running=False,
            belt_status="idle",
            message="Belt calibration test stopped",
        )
        return self.get_state()

    def stop_sorter_calibration(self):
        thread = None
        with self._lock:
            if self._sorter_calibration_stop_event is not None:
                self._sorter_calibration_stop_event.set()
            if self._sorter_calibration_commands is not None:
                self._sorter_calibration_commands.put({"type": "label", "label": "q"})
            thread = self._sorter_calibration_thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        self._update_state(
            sorter_calibration_running=False,
            sorter_calibration_prompt="Sorter calibration stopped.",
            sorter_calibration_sample=None,
            sorting_enabled=False,
            sorter_running=False,
            message="Sorter calibration stopped",
        )
        return self.get_state()

    def update_belt_settings(
        self,
        speed=None,
        accel=None,
        steps=None,
        launch_speed=None,
        launch_accel=None,
        launch_steps=None,
        clear_thresh=None,
        post_detect_delay_ms=None,
        detect_integration_ms=None,
        detect_samples=None,
        detect_streak=None,
        game_belt_enabled=None,
    ):
        changes = {}
        if speed is not None:
            changes["belt_speed"] = int(speed)
        if accel is not None:
            changes["belt_accel"] = int(accel)
        changes["belt_steps"] = None if steps is None else int(steps)
        if launch_speed is not None:
            changes["belt_launch_speed"] = int(launch_speed)
        if launch_accel is not None:
            changes["belt_launch_accel"] = int(launch_accel)
        if launch_steps is not None:
            changes["belt_launch_steps"] = max(1, int(launch_steps))
        if clear_thresh is not None:
            changes["belt_clear_thresh"] = float(clear_thresh)
        if post_detect_delay_ms is not None:
            changes["belt_post_detect_delay_ms"] = int(post_detect_delay_ms)
        if detect_integration_ms is not None:
            changes["belt_detect_integration_ms"] = max(2, int(detect_integration_ms))
        if detect_samples is not None:
            changes["belt_detect_samples"] = max(1, int(detect_samples))
        if detect_streak is not None:
            changes["belt_detect_streak"] = max(1, int(detect_streak))
        if game_belt_enabled is not None:
            changes["game_belt_enabled"] = bool(game_belt_enabled)
        if changes:
            self._update_state(**changes)
        return self.get_state()

    def start_belt_calibration(self):
        state = self.get_state()
        integration_ms = int(state["belt_detect_integration_ms"])
        try:
            from FullSubsystems.belt import open_belt_tcs34725

            sensor = open_belt_tcs34725(integration_time_ms=integration_ms, gain=4)
        except Exception as exc:
            self._update_state(
                belt_calibration_running=False,
                belt_calibration_prompt=f"Failed to open belt sensor: {exc}",
                belt_calibration_last_sample=None,
                message="Belt calibration failed",
                error=str(exc),
            )
            return self.get_state()

        with self._lock:
            self._belt_calibration_sensor = sensor
            self._belt_calibration_empty_samples = []
            self._belt_calibration_piece_samples = []

        self._update_state(
            belt_calibration_running=True,
            belt_calibration_prompt="Capture empty and piece-covered samples, then finish calibration.",
            belt_calibration_last_sample=None,
            belt_calibration_counts={"empty": 0, "piece": 0},
            message="Belt calibration active",
            error=None,
        )
        return self.get_state()

    def submit_belt_calibration_action(self, action):
        sensor = None
        with self._lock:
            sensor = self._belt_calibration_sensor

        if action == "cancel":
            with self._lock:
                self._belt_calibration_sensor = None
                self._belt_calibration_empty_samples = []
                self._belt_calibration_piece_samples = []
            self._update_state(
                belt_calibration_running=False,
                belt_calibration_prompt="Belt calibration cancelled.",
                belt_calibration_last_sample=None,
                message="Belt calibration cancelled",
            )
            return self.get_state()

        if sensor is None:
            return self.get_state()

        if action in {"empty", "piece"}:
            state = self.get_state()
            sample = self._read_belt_color_sample(
                sensor,
                count=max(1, int(state["belt_detect_samples"])),
                delay_s=BELT_DETECT_SAMPLE_DELAY_S,
            )
            with self._lock:
                if action == "empty":
                    self._belt_calibration_empty_samples.append(sample)
                else:
                    self._belt_calibration_piece_samples.append(sample)
                empty_count = len(self._belt_calibration_empty_samples)
                piece_count = len(self._belt_calibration_piece_samples)
            self._update_state(
                belt_calibration_running=True,
                belt_calibration_last_sample=sample,
                belt_calibration_counts={"empty": empty_count, "piece": piece_count},
                belt_calibration_prompt="Capture more samples or finish calibration.",
                message=f"Captured belt {action} sample",
                error=None,
            )
            return self.get_state()

        if action == "finish":
            with self._lock:
                empty_samples = list(self._belt_calibration_empty_samples)
                piece_samples = list(self._belt_calibration_piece_samples)
                self._belt_calibration_sensor = None
                self._belt_calibration_empty_samples = []
                self._belt_calibration_piece_samples = []

            if not empty_samples or not piece_samples:
                self._update_state(
                    belt_calibration_running=False,
                    belt_calibration_prompt="Need at least one empty sample and one piece sample.",
                    message="Belt calibration incomplete",
                )
                return self.get_state()

            piece_clear_values = [sample["clear"] for sample in piece_samples]
            empty_clear_values = [sample["clear"] for sample in empty_samples]
            piece_avg = sum(piece_clear_values) / len(piece_clear_values)
            empty_avg = sum(empty_clear_values) / len(empty_clear_values)
            piece_is_lower = piece_avg < empty_avg

            if piece_is_lower:
                clear_thresh = (max(piece_clear_values) + min(empty_clear_values)) / 2.0
                detect_mode = "below"
            else:
                clear_thresh = (min(piece_clear_values) + max(empty_clear_values)) / 2.0
                detect_mode = "above"

            self._update_state(
                belt_calibration_running=False,
                belt_calibration_prompt=(
                    f"Calibration complete. Suggested clear threshold {clear_thresh:.1f} "
                    f"(detect piece when clear is {detect_mode} threshold)."
                ),
                belt_clear_thresh=clear_thresh,
                belt_detect_mode=detect_mode,
                belt_calibration_counts={"empty": len(empty_samples), "piece": len(piece_samples)},
                message=f"Belt calibration complete. Suggested clear threshold {clear_thresh:.1f}",
                error=None,
            )
            return self.get_state()

        return self.get_state()

    def start_gate(self, speed=GATE_DEFAULT_SPEED, accel=GATE_DEFAULT_ACCEL, steps=None):
        with self._lock:
            if self._gate_thread and self._gate_thread.is_alive():
                return self._state.to_dict()
            self._gate_stop_event = threading.Event()
            worker = GateWorker(
                controller=self,
                stop_event=self._gate_stop_event,
                speed=speed,
                accel=accel,
                steps=steps,
            )
            self._gate_thread = threading.Thread(
                target=worker.run,
                daemon=True,
                name="gate-worker",
            )
            self._gate_thread.start()
            self._update_state(
                gate_running=True,
                gate_status="starting",
                gate_mode="steps" if steps is not None else "continuous",
                gate_speed=speed,
                gate_accel=accel,
                gate_steps=steps,
                gate_error=None,
                message="Starting gate stepper",
            )
            return self._state.to_dict()

    def stop_gate(self):
        thread = None
        with self._lock:
            if self._gate_stop_event is not None:
                self._gate_stop_event.set()
            thread = self._gate_thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        self._update_state(
            gate_running=False,
            gate_status="stopped",
            message="Gate stepper stopped",
        )
        return self.get_state()

    def get_state(self):
        with self._lock:
            if self._sorter_process is not None and self._sorter_process.poll() is not None:
                self._sorter_process = None
                self._state.sorter_running = False
                self._state.sorting_enabled = False
                if self._state.message == "Sorter enabled":
                    self._state.message = "Sorter completed"
            return self._state.to_dict()

    def get_runtime_log(self):
        with self._lock:
            return {"runtime_log": list(self._state.runtime_log)}

    def _update_state(self, **changes):
        with self._lock:
            previous_values = {key: getattr(self._state, key, None) for key in changes}
            for key, value in changes.items():
                setattr(self._state, key, value)
            self._log_state_changes_locked(previous_values, changes)
            self._state.updated_at = time.time()

    def start_game(self, camera=None, device=None, width=640, height=480, depth=5, state_streak=3):
        with self._lock:
            if self._belt_test_thread and self._belt_test_thread.is_alive():
                self._update_state(message="Stop belt calibration test before starting the game")
                return self._state.to_dict()
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
                game_paused=False,
                game_status="starting",
                message="Starting game loop",
                error=None,
            )
            return self._state.to_dict()

    def toggle_pause_game(self):
        with self._lock:
            if not (self._game_thread and self._game_thread.is_alive()):
                return self._state.to_dict()
            paused = bool(self._state.game_paused)
            if self._game_commands is None:
                return self._state.to_dict()
            if paused:
                self._game_commands.put({"type": "resume"})
                self._update_state(
                    game_paused=False,
                    message="Resuming game loop",
                )
            else:
                self._game_commands.put({"type": "pause"})
                self._update_state(
                    game_paused=True,
                    message="Game paused",
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
            game_paused=False,
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

    def reboot_runtime(self):
        self.stop_game()
        self.stop_belt_test()
        self.stop_belt()
        self.stop_gate()
        self.disable_sorting()
        self.stop_sorter_calibration()

        with self._lock:
            if self._belt_calibration_sensor is not None:
                try:
                    self._belt_calibration_sensor.deinit()
                except Exception:
                    pass
                self._belt_calibration_sensor = None
            self._belt_calibration_empty_samples = []
            self._belt_calibration_piece_samples = []

        self._update_state(
            game_running=False,
            game_paused=False,
            game_status="idle",
            game_phase="idle",
            turn_state="idle",
            awaiting_confirmation=None,
            prompt=None,
            error=None,
            winner=0,
            tracker_active=False,
            tracker_calibrated=False,
            camera_source=None,
            current_board=[[0] * 7 for _ in range(6)],
            confirmed_board=[[0] * 7 for _ in range(6)],
            suggested_red_column=None,
            detected_yellow_column=None,
            confirmed_red_count=0,
            confirmed_yellow_count=0,
            pending_yellow_count=0,
            belt_running=False,
            belt_status="idle",
            belt_mode="continuous",
            belt_error=None,
            belt_calibration_running=False,
            belt_calibration_prompt="Belt calibration stopped.",
            belt_calibration_last_sample=None,
            belt_test_running=False,
            belt_test_waiting_continue=False,
            belt_test_prompt="Belt calibration test stopped.",
            belt_piece_ready=False,
            belt_ready_confirmed=False,
            gate_running=False,
            gate_status="idle",
            gate_error=None,
            message="Runtime rebooted. Saved settings and calibration values were preserved.",
        )
        return self.get_state()

    def enable_sorting(self, max_sorted=None):
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

        extra_args = []
        if max_sorted is not None:
            extra_args.extend(["--max-sorted", str(max_sorted)])
        cmd = [sys.executable, str(ROOT_DIR / "FullSubsystems" / "sorter.py"), *runtime_args, *extra_args]
        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._sorter_process = process
        message = "Sorter enabled" if max_sorted is None else f"Sorter enabled for {max_sorted} pieces"
        self._update_state(sorting_enabled=True, sorter_running=True, message=message)
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

    def remove_piece(self, row, column):
        if self._game_commands is None:
            return self.get_state()
        self._game_commands.put({"type": "remove_piece", "row": row, "column": column})
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
            game_paused=False,
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
        self._deferred_commands = []
        self._belt_feeder = None

    def _set_drop_servo(self, servo_pca, current_channel, visible_column):
        if servo_pca is None:
            return current_channel

        next_channel = drop_servo_channel_for_visible_column(visible_column)
        if current_channel is not None and current_channel != next_channel:
            move_game_servo(servo_pca, current_channel, 0)

        if next_channel is not None and next_channel != current_channel:
            move_game_servo(servo_pca, next_channel, DROP_SERVO_ANGLE)
        elif next_channel is None and current_channel is not None:
            move_game_servo(servo_pca, current_channel, 0)

        return next_channel

    def _reset_drop_servo(self, servo_pca, current_channel):
        if servo_pca is None or current_channel is None:
            return None
        move_game_servo(servo_pca, current_channel, 0)
        return None

    def _sanitize_robot_turn_board(self, confirmed_board, observed_board):
        sanitized = np.copy(observed_board)
        confirmed = np.asarray(confirmed_board)
        # Never let new yellow pieces appear during the robot turn.
        sanitized[(confirmed != 2) & (sanitized == 2)] = 0
        # Preserve any already-confirmed yellow cells.
        sanitized[confirmed == 2] = 2
        return sanitized

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

    def _remove_piece_from_board(self, board_state, row, visible_column):
        internal_column = internal_column_from_user(np.asarray(board_state), visible_column)
        next_board = np.copy(board_state)
        if row < 0 or row >= next_board.shape[0]:
            return None
        if internal_column < 0 or internal_column >= next_board.shape[1]:
            return None
        if next_board[row, internal_column] == 0:
            return None
        for current_row in range(row, 0, -1):
            next_board[current_row, internal_column] = next_board[current_row - 1, internal_column]
        next_board[0, internal_column] = 0
        return next_board

    def _read_belt_color_sample(self, sensor, count=8, delay_s=0.04):
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

    def _drain_commands(self):
        commands = list(self._deferred_commands)
        self._deferred_commands = []
        while True:
            try:
                commands.append(self.commands.get_nowait())
            except queue.Empty:
                return commands

    def _wait_while_paused(self, pause_message="Game paused"):
        state_before_pause = self.controller.get_state()
        resume_state = {
            "game_status": state_before_pause["game_status"],
            "game_phase": state_before_pause["game_phase"],
            "turn_state": state_before_pause["turn_state"],
            "awaiting_confirmation": state_before_pause["awaiting_confirmation"],
            "prompt": state_before_pause["prompt"],
            "message": state_before_pause["message"],
            "suggested_red_column": state_before_pause["suggested_red_column"],
            "detected_yellow_column": state_before_pause["detected_yellow_column"],
        }
        self.controller._update_state(
            game_paused=True,
            game_status="paused",
            game_phase="paused",
            turn_state="paused",
            prompt="Resume when you're ready.",
            message=pause_message,
        )
        while not self.stop_event.is_set():
            try:
                command = self.commands.get(timeout=0.1)
            except queue.Empty:
                continue
            command_type = command["type"]
            if command_type == "stop":
                self.stop_event.set()
                return False
            if command_type == "resume":
                self.controller._update_state(
                    game_paused=False,
                    **resume_state,
                )
                return True
            if command_type != "pause":
                self._deferred_commands.append(command)
        return False

    def _maybe_handle_runtime_command(self, command, pause_message="Game paused", on_pause=None):
        command_type = command["type"]
        if command_type == "stop":
            self.stop_event.set()
            return "stop"
        if command_type == "pause":
            if on_pause is not None:
                on_pause()
            resumed = self._wait_while_paused(pause_message=pause_message)
            return "resume" if resumed else "stop"
        return None

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
                runtime_result = self._maybe_handle_runtime_command(
                    command,
                    pause_message="Game paused during yellow confirmation",
                    on_pause=self._pause_runtime_subsystems,
                )
                if runtime_result == "stop":
                    return None
                if runtime_result == "resume":
                    continue
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
                if command["type"] == "remove_piece":
                    corrected = self._remove_piece_from_board(
                        self.confirmed_board,
                        command["row"],
                        command["column"],
                    )
                    if corrected is not None:
                        return corrected
            time.sleep(0.1)
        return None

    def _await_red_confirmation(self, cap, tracker, confirmed_board, ai_expected_board, ai_visible_column, manual_drop=False):
        self.controller._update_state(
            game_status="awaiting_red_confirmation",
            game_phase="robot_confirmation",
            turn_state="robot_waiting_for_placement",
            awaiting_confirmation="red",
            suggested_red_column=ai_visible_column,
            prompt=(
                (
                    f"Manually drop RED into the top of column {ai_visible_column}, then confirm it in the app."
                    if manual_drop
                    else f"Place RED in column {ai_visible_column}. Vision will confirm it automatically when it sees the correct placement."
                )
            ),
            message="Waiting for manual RED placement" if manual_drop else "Waiting for RED placement",
        )
        red_last_seen_board = None
        red_stable_board = None
        red_stable_streak = 0
        while not self.stop_event.is_set():
            for command in self._drain_commands():
                runtime_result = self._maybe_handle_runtime_command(
                    command,
                    pause_message="Game paused during red confirmation",
                    on_pause=self._pause_runtime_subsystems,
                )
                if runtime_result == "stop":
                    return None
                if runtime_result == "resume":
                    continue
                if command["type"] == "confirm_red":
                    return np.copy(ai_expected_board)
                if command["type"] == "remove_piece":
                    corrected = self._remove_piece_from_board(
                        confirmed_board,
                        command["row"],
                        command["column"],
                    )
                    if corrected is not None:
                        return corrected
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            _, _, _ = tracker.process_frame(frame)
            raw_board_copy = np.copy(tracker.board_state)
            board_copy = self._sanitize_robot_turn_board(confirmed_board, raw_board_copy)

            if boards_equal(board_copy, red_last_seen_board):
                red_stable_streak += 1
            else:
                red_last_seen_board = np.copy(board_copy)
                red_stable_streak = 1

            if red_stable_streak >= self.state_streak:
                red_stable_board = np.copy(board_copy)

            pending_red_count = max(
                0,
                int(np.count_nonzero(board_copy == 1)) - int(np.count_nonzero(np.asarray(confirmed_board) == 1)),
            )
            self.controller._update_state(
                tracker_active=tracker.is_board_active,
                tracker_calibrated=tracker.is_calibrated,
                current_board=board_to_lists(board_copy),
                winner=tracker.winner,
                pending_yellow_count=0,
                message=(
                    "Waiting for RED placement"
                    if pending_red_count == 0
                    else f"Checking RED placement in column {ai_visible_column}"
                ),
            )

            if red_stable_board is None:
                time.sleep(0.05)
                continue

            if boards_equal(red_stable_board, ai_expected_board):
                return np.copy(ai_expected_board)

            legal_red, _ = legal_ai_transition(confirmed_board, red_stable_board)
            if legal_red:
                added = find_single_added_piece(confirmed_board, red_stable_board, 1)
                if added is not None:
                    _, observed_internal_col = added
                    observed_visible_col = user_visible_column(red_stable_board, observed_internal_col)
                    self.controller._update_state(
                        prompt=(
                            f"Vision sees RED in column {observed_visible_col}, "
                            f"but the expected column is {ai_visible_column}. "
                            "Adjust the piece or use manual confirm if the board is correct."
                        ),
                        message=f"Observed RED in column {observed_visible_col}; waiting for expected column",
                    )
            time.sleep(0.05)
        return None

    def _wait_for_serial(self, arduino, targets, timeout_s=5.0):
        deadline = time.time() + timeout_s
        while True:
            if self.stop_event.is_set():
                raise RuntimeError("Game loop stopping")
            if time.time() > deadline:
                raise TimeoutError(f"Timeout waiting for {targets}")
            line = arduino.readline().decode(errors="ignore").strip()
            line = "".join(ch for ch in line if ch.isprintable())
            if line in targets:
                return line

    def _send_serial_cmd(self, arduino, command, targets, timeout_s=5.0, attempts=3, pre_delay_s=0.1):
        last_error = None
        for _ in range(attempts):
            time.sleep(pre_delay_s)
            arduino.write(f"{command}\n".encode())
            try:
                return self._wait_for_serial(arduino, targets, timeout_s=timeout_s)
            except TimeoutError as exc:
                last_error = exc
                arduino.reset_input_buffer()
                time.sleep(0.2)
        raise last_error

    def _sync_serial_controller(self, arduino, attempts=6, timeout_s=1.5):
        for _ in range(attempts):
            arduino.write(b"PING\n")
            try:
                self._wait_for_serial(arduino, {"PONG"}, timeout_s=timeout_s)
                time.sleep(0.3)
                arduino.reset_input_buffer()
                return
            except TimeoutError:
                arduino.reset_input_buffer()
                time.sleep(0.3)
        raise TimeoutError("Controller did not respond to PING")

    def _run_gate_steps(self, steps, speed=GATE_DEFAULT_SPEED, accel=GATE_DEFAULT_ACCEL):
        import serial

        self.controller._update_state(
            gate_running=True,
            gate_status="running",
            gate_mode="steps",
            gate_speed=speed,
            gate_accel=accel,
            gate_steps=steps,
            gate_error=None,
        )
        with self.controller._arduino_lock:
            arduino = serial.Serial(GATE_PORT, 9600, timeout=1)
            try:
                time.sleep(2)
                arduino.reset_input_buffer()
                arduino.reset_output_buffer()
                self._sync_serial_controller(arduino)
                self._send_serial_cmd(arduino, f"GATE SPEED {speed}", {"OK", "ERR"})
                self._send_serial_cmd(arduino, f"GATE ACCEL {accel}", {"OK", "ERR"})
                self._send_serial_cmd(arduino, f"GATE STEPS {steps}", {"DONE"}, timeout_s=12.0)
            finally:
                arduino.close()
        self.controller._update_state(
            gate_running=False,
            gate_status="completed",
            gate_error=None,
        )

    def _move_gate_out_if_needed(self):
        with self.controller._lock:
            if self.controller._gate_is_out:
                return
        self.controller._update_state(message="Moving clear gate out of the board")
        self._run_gate_steps(GATE_DEFAULT_STEPS)
        with self.controller._lock:
            self.controller._gate_is_out = True
        self.controller._update_state(message="Clear gate moved out of the board")

    def _move_gate_in_if_needed(self):
        with self.controller._lock:
            if not self.controller._gate_is_out:
                return
        self.controller._update_state(message="Moving clear gate back into position")
        self._run_gate_steps(-GATE_DEFAULT_STEPS)
        with self.controller._lock:
            self.controller._gate_is_out = False
        self.controller._update_state(message="Clear gate returned to position")

    def _deliver_red_piece_with_belt(self):
        from FullSubsystems.belt import open_belt_tcs34725
        import serial

        state = self.controller.get_state()
        stage_speed = BELT_STAGE_SPEED
        stage_accel = int(state["belt_accel"])
        launch_speed = int(state["belt_launch_speed"])
        launch_accel = int(state["belt_launch_accel"])
        launch_steps = int(state["belt_launch_steps"])
        clear_thresh = float(state["belt_clear_thresh"])
        detect_mode = state["belt_detect_mode"]
        detect_integration_ms = int(state["belt_detect_integration_ms"])
        detect_samples = int(state["belt_detect_samples"])
        detect_streak_target = int(state["belt_detect_streak"])

        sensor = open_belt_tcs34725(integration_time_ms=detect_integration_ms, gain=4)
        detect_streak = 0
        deadline = time.time() + 12.0
        stage_running = False

        self.controller._update_state(
            belt_running=True,
            belt_status="staging",
            belt_mode="continuous",
            belt_speed=stage_speed,
            belt_accel=stage_accel,
            belt_error=None,
            message="Checking for staged red piece at belt sensor",
        )

        with self.controller._arduino_lock:
            arduino = serial.Serial(GATE_PORT, 9600, timeout=1)
            try:
                time.sleep(2)
                arduino.reset_input_buffer()
                arduino.reset_output_buffer()
                self._sync_serial_controller(arduino)
                self._send_serial_cmd(arduino, f"SPEED {stage_speed}", {"OK", "ERR"})
                self._send_serial_cmd(arduino, f"ACCEL {stage_accel}", {"OK", "ERR"})

                while not self.stop_event.is_set():
                    for command in self._drain_commands():
                        runtime_result = self._maybe_handle_runtime_command(
                            command,
                            pause_message="Game paused; belt feed stopped",
                            on_pause=lambda: self._pause_belt_motion(arduino),
                        )
                        if runtime_result == "stop":
                            self.controller._update_state(
                                belt_running=False,
                                belt_status="paused",
                                message="Game stopped during belt feed",
                            )
                            return
                        if runtime_result == "resume":
                            deadline = time.time() + 12.0
                            detect_streak = 0
                            self.controller._update_state(
                                belt_running=True,
                                belt_status="staging",
                                belt_mode="continuous",
                                belt_speed=stage_speed,
                                belt_accel=stage_accel,
                                message="Resuming belt staging",
                            )
                            if stage_running:
                                self._send_serial_cmd(arduino, f"RUN {stage_speed}", {"OK", "ERR"})
                    sample = self._read_belt_color_sample(
                        sensor,
                        count=detect_samples,
                        delay_s=BELT_DETECT_SAMPLE_DELAY_S,
                    )
                    clear_value = sample["clear"]
                    covered = (
                        clear_value <= clear_thresh
                        if detect_mode == "below"
                        else clear_value >= clear_thresh
                    )
                    if covered:
                        detect_streak += 1
                    else:
                        detect_streak = 0

                    if not covered and not stage_running:
                        self._send_serial_cmd(arduino, f"RUN {stage_speed}", {"OK", "ERR"})
                        stage_running = True
                        self.controller._update_state(
                            belt_running=True,
                            belt_status="staging",
                            belt_mode="continuous",
                            belt_speed=stage_speed,
                            belt_accel=stage_accel,
                            message="No staged red piece yet; feeding slowly toward the sensor",
                        )

                    self.controller._update_state(
                        belt_running=True,
                        belt_status="staging",
                        belt_mode="continuous",
                        message=(
                            f"Waiting for staged piece at belt sensor (clear={clear_value:.1f}, "
                            f"threshold={clear_thresh:.1f}, mode={detect_mode}, "
                            f"int={detect_integration_ms}ms, samples={detect_samples}, streak={detect_streak_target})"
                        ),
                    )

                    if detect_streak >= detect_streak_target:
                        if stage_running:
                            self._send_serial_cmd(arduino, "STOP", {"OK"}, timeout_s=2.0)
                            stage_running = False
                        self.controller._update_state(
                            belt_running=False,
                            belt_status="ready",
                            belt_mode="continuous",
                            message=(
                                f"Red piece staged at clear={clear_value:.1f}. Launching into column."
                            ),
                        )
                        self._send_serial_cmd(arduino, f"SPEED {launch_speed}", {"OK", "ERR"})
                        self._send_serial_cmd(arduino, f"ACCEL {launch_accel}", {"OK", "ERR"})
                        self.controller._update_state(
                            belt_running=True,
                            belt_status="launching",
                            belt_mode="steps",
                            belt_speed=launch_speed,
                            belt_accel=launch_accel,
                            belt_steps=launch_steps,
                            message=(
                                f"Launching red piece at {launch_speed} speed, {launch_accel} accel, "
                                f"{launch_steps} steps"
                            ),
                        )
                        self._send_serial_cmd(arduino, f"RUNSTEPS {launch_steps}", {"DONE"}, timeout_s=12.0)
                        self.controller._update_state(
                            belt_running=False,
                            belt_status="completed",
                            belt_mode="steps",
                            belt_error=None,
                            message=(
                                f"Staged red piece launched {launch_steps} steps at speed {launch_speed}"
                            ),
                        )
                        return

                    if time.time() > deadline:
                        raise TimeoutError(
                            f"Belt sensor did not detect a covered piece before timeout "
                            f"(threshold={clear_thresh:.1f}, mode={detect_mode})"
                        )
            finally:
                try:
                    arduino.close()
                except Exception:
                    pass

    def _pause_belt_motion(self, arduino):
        try:
            self._send_serial_cmd(arduino, "STOP", {"OK"}, timeout_s=2.0, attempts=1)
        except Exception:
            pass
        self.controller._update_state(
            belt_running=False,
            belt_status="paused",
            belt_mode="continuous",
            message="Game paused; belt stopped",
        )

    def _sync_belt_feeder_mode(self):
        desired = bool(self.controller.get_state()["game_belt_enabled"])
        if desired and self._belt_feeder is None:
            feeder = GameLoopBeltFeeder(self.controller, self.stop_event)
            feeder.start()
            self._belt_feeder = feeder
            self.controller._active_belt_feeder = feeder
        elif not desired and self._belt_feeder is not None:
            self._belt_feeder.stop()
            self._belt_feeder = None
            self.controller._active_belt_feeder = None

    def _disable_belt_feeder(self):
        if self._belt_feeder is not None:
            self._belt_feeder.stop()
            self._belt_feeder = None
            self.controller._active_belt_feeder = None

    def _pause_runtime_subsystems(self):
        if self._belt_feeder is not None:
            self._belt_feeder.pause()

    def _resume_runtime_subsystems(self):
        if self._belt_feeder is not None:
            self._belt_feeder.resume()

    def _complete_game(self, message, confirmed_board, winner=0):
        if self._belt_feeder is not None:
            self._disable_belt_feeder()
        sorted_target = int(np.count_nonzero(confirmed_board != 0)) + 5
        self._move_gate_out_if_needed()
        self.controller.enable_sorting(max_sorted=sorted_target)
        self.controller._update_state(
            game_status="finished",
            game_phase="complete",
            turn_state="game_over",
            awaiting_confirmation=None,
            prompt=None,
            detected_yellow_column=None,
            suggested_red_column=None,
            message=f"{message} Post-game sorting started for {sorted_target} pieces.",
            winner=winner,
        )

    def run(self):
        cap = None
        servo_pca = None
        tracker = Connect4Tracker()
        remaining_candidates = []
        camera_source = None
        failed_reads = 0
        recovery_cycles = 0
        active_drop_servo_channel = None
        confirmed_board = None
        last_seen_board = None
        stable_streak = 0
        stable_board = None
        last_calibration_log_at = 0.0

        try:
            self._move_gate_in_if_needed()

            try:
                import board
                import busio
                from adafruit_pca9685 import PCA9685

                i2c_pca = busio.I2C(board.SCL, board.SDA)
                servo_pca = PCA9685(i2c_pca)
                servo_pca.frequency = 50
                for channel in range(6):
                    move_game_servo(servo_pca, channel, 0)
            except Exception as exc:
                servo_pca = None
                self.controller._update_state(
                    message=f"Game loop started without drop-servo control: {exc}",
                    error=None,
                )

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
                if tracker.is_calibrated and confirmed_board is not None:
                    self._sync_belt_feeder_mode()
                else:
                    self._disable_belt_feeder()
                for command in self._drain_commands():
                    runtime_result = self._maybe_handle_runtime_command(
                        command,
                        on_pause=self._pause_runtime_subsystems,
                    )
                    if runtime_result == "stop":
                        self.stop_event.set()
                        break
                    if runtime_result == "resume":
                        self._resume_runtime_subsystems()
                        continue
                if self.stop_event.is_set():
                    break
                if self.controller.get_state()["game_paused"]:
                    time.sleep(0.05)
                    continue

                ret, frame = cap.read()
                if not ret:
                    failed_reads += 1
                    read_failure_threshold = 10 if tracker.is_board_active and not tracker.is_calibrated else 5
                    if failed_reads < read_failure_threshold:
                        time.sleep(0.1)
                        continue

                    recovery_cycles += 1
                    if recovery_cycles > 3:
                        raise RuntimeError(
                            f"Camera repeatedly failed to recover on {camera_source}. "
                            "Check the USB camera connection and restart the game loop."
                        )

                    self.controller._update_state(
                        message=(
                            f"Camera read failed {failed_reads} times; reopening {camera_source}"
                        )
                    )
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
                display_board_copy = np.copy(board_copy)
                if confirmed_board is not None:
                    state_view = self.controller.get_state()
                    if (
                        state_view["game_status"] == "thinking"
                        or state_view["awaiting_confirmation"] == "red"
                        or str(state_view["turn_state"]).startswith("robot_")
                    ):
                        display_board_copy = self._sanitize_robot_turn_board(confirmed_board, board_copy)

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
                    current_board=board_to_lists(display_board_copy),
                    winner=tracker.winner,
                    pending_yellow_count=max(
                        0,
                        int(np.count_nonzero(display_board_copy == 2))
                        - int(np.count_nonzero(np.asarray(confirmed_board) == 2)) if confirmed_board is not None else 0,
                    ),
                )

                if not tracker.is_calibrated:
                    calibration_message = (
                        "Board not detected yet; keep the full empty board visible"
                        if not tracker.is_board_active
                        else "Board detected; calibrating empty board"
                    )
                    self.controller._update_state(
                        game_status="calibrating",
                        game_phase="calibrating",
                        turn_state="booting",
                        message=calibration_message,
                    )
                    now = time.time()
                    if now - last_calibration_log_at >= 3.0:
                        self.controller.log_event(
                            "Calibration heartbeat: "
                            f"tracker_active={tracker.is_board_active}, "
                            f"tracker_calibrated={tracker.is_calibrated}, "
                            f"stable_streak={stable_streak}, "
                            f"message={calibration_message}"
                        )
                        last_calibration_log_at = now
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
                    self._sync_belt_feeder_mode()
                    continue

                self.confirmed_board = confirmed_board

                manual_applied = False
                for command in self._drain_commands():
                    runtime_result = self._maybe_handle_runtime_command(command)
                    runtime_result = self._maybe_handle_runtime_command(
                        command,
                        on_pause=self._pause_runtime_subsystems,
                    )
                    if runtime_result == "stop":
                        self.stop_event.set()
                        break
                    if runtime_result == "resume":
                        self._resume_runtime_subsystems()
                        continue
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
                    elif command["type"] == "remove_piece":
                        corrected_board = self._remove_piece_from_board(
                            confirmed_board,
                            command["row"],
                            command["column"],
                        )
                        if corrected_board is not None:
                            confirmed_board = corrected_board
                            self.confirmed_board = confirmed_board
                            self._sync_tracker_board(tracker, confirmed_board)
                            stable_board = np.copy(confirmed_board)
                            last_seen_board = np.copy(confirmed_board)
                            stable_streak = self.state_streak
                            manual_applied = True
                            self.controller._update_state(
                                game_phase="live",
                                turn_state="board_corrected",
                                message=(
                                    f"Removed confirmed piece at row {command['row']}, "
                                    f"column {command['column']}"
                                ),
                            )
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
                    self._complete_game("YELLOW wins", confirmed_board, winner=2)
                    break
                if board_full(confirmed_board):
                    self._complete_game("Board full: draw", confirmed_board)
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
                use_belt = bool(self.controller.get_state()["game_belt_enabled"])
                self.controller._update_state(
                    suggested_red_column=visible_red_col,
                    game_status="ready_for_launch",
                    game_phase="robot_launch",
                    turn_state="robot_ready_for_launch",
                    prompt=(
                        (
                            f"RED column {visible_red_col} selected. "
                            "Confirm the staged piece if the belt has stopped at the sensor, or wait for one to arrive."
                        )
                        if use_belt
                        else f"RED column {visible_red_col} selected. Drop the piece manually into the top of that column."
                    ),
                    message=f"Computer chose RED column {visible_red_col} (score={score})",
                )
                active_drop_servo_channel = self._set_drop_servo(
                    servo_pca,
                    active_drop_servo_channel,
                    visible_red_col,
                )
                if use_belt:
                    self._sync_belt_feeder_mode()
                    if self._belt_feeder is None:
                        raise RuntimeError("Game belt staging worker is unavailable")
                    self._belt_feeder.launch_piece(
                        int(self.controller.get_state()["belt_launch_speed"]),
                        int(self.controller.get_state()["belt_launch_accel"]),
                        int(self.controller.get_state()["belt_launch_steps"]),
                    )
                else:
                    if self._belt_feeder is not None:
                        self._belt_feeder.stop()
                        self._belt_feeder = None
                        self.controller._active_belt_feeder = None
                    self.controller._update_state(
                        message=f"Manual red drop mode active for column {visible_red_col}",
                        belt_running=False,
                        belt_status="idle",
                    )
                maybe_red_board = self._await_red_confirmation(
                    cap,
                    tracker,
                    confirmed_board,
                    ai_expected_board,
                    visible_red_col,
                    manual_drop=not use_belt,
                )
                active_drop_servo_channel = self._reset_drop_servo(
                    servo_pca,
                    active_drop_servo_channel,
                )
                if maybe_red_board is None:
                    break
                confirmed_board = np.copy(maybe_red_board)
                self.confirmed_board = confirmed_board
                self._sync_tracker_board(tracker, confirmed_board)
                stable_board = np.copy(confirmed_board)
                last_seen_board = np.copy(confirmed_board)
                stable_streak = self.state_streak

                if board_winner(confirmed_board) == 1:
                    self._complete_game("RED wins", confirmed_board, winner=1)
                    break
                if board_full(confirmed_board):
                    self._complete_game("Board full: draw", confirmed_board)
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
            self._disable_belt_feeder()
            active_drop_servo_channel = self._reset_drop_servo(
                servo_pca,
                active_drop_servo_channel,
            )
            if cap is not None:
                cap.release()
            if servo_pca is not None:
                servo_pca.deinit()

class GameLoopBeltFeeder:
    PORT = "/dev/serial0"

    def __init__(self, controller, parent_stop_event):
        self.controller = controller
        self.parent_stop_event = parent_stop_event
        self.stop_event = threading.Event()
        self.commands = queue.Queue()
        self.thread = None
        self._launch_done = threading.Event()
        self._launch_error = None
        self._paused = False
        self._ready_confirmed = False

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run, daemon=True, name="game-belt-feeder")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.commands.put({"type": "stop"})
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)

    def pause(self):
        self.commands.put({"type": "pause"})

    def resume(self):
        self.commands.put({"type": "resume"})

    def confirm_ready(self, accept=True):
        self.commands.put({"type": "confirm_ready" if accept else "reject_ready"})

    def launch_piece(self, launch_speed, launch_accel, launch_steps, timeout_s=90.0):
        self._launch_error = None
        self._launch_done.clear()
        self.commands.put(
            {
                "type": "launch",
                "launch_speed": int(launch_speed),
                "launch_accel": int(launch_accel),
                "launch_steps": int(launch_steps),
            }
        )
        if not self._launch_done.wait(timeout=timeout_s):
            raise TimeoutError("Timed out waiting for staged and confirmed belt launch")
        if self._launch_error:
            raise RuntimeError(self._launch_error)

    def _wait_for(self, arduino, targets, timeout_s=5.0):
        deadline = time.time() + timeout_s
        while True:
            if self.stop_event.is_set() or self.parent_stop_event.is_set():
                raise RuntimeError("Game belt feeder stopping")
            if time.time() > deadline:
                raise TimeoutError(f"Timeout waiting for {targets}")
            line = arduino.readline().decode(errors="ignore").strip()
            line = "".join(ch for ch in line if ch.isprintable())
            if line and line not in targets:
                self.controller.log_event(f"Belt feeder serial RX: {line}")
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
        for attempt in range(1, attempts + 1):
            self.controller.log_event(f"Belt feeder PING attempt {attempt}/{attempts}")
            arduino.write(b"PING\n")
            try:
                self._wait_for(arduino, {"PONG"}, timeout_s=timeout_s)
                time.sleep(0.3)
                arduino.reset_input_buffer()
                self.controller.log_event("Belt feeder controller responded with PONG")
                return
            except TimeoutError:
                arduino.reset_input_buffer()
                time.sleep(0.3)
        raise TimeoutError("Controller did not respond to PING")

    def _open_controller_session(self, serial_module, session_attempts=6):
        last_error = None
        for attempt in range(1, session_attempts + 1):
            arduino = None
            try:
                self.controller._update_state(
                    belt_running=False,
                    belt_status="starting",
                    belt_error=None,
                    message=(
                        "Connecting belt feeder controller"
                        if attempt == 1
                        else f"Retrying belt feeder controller connection ({attempt}/{session_attempts})"
                    ),
                )
                self.controller.log_event(
                    f"Opening belt feeder serial session on {self.PORT} (attempt {attempt}/{session_attempts})"
                )
                arduino = serial_module.Serial(self.PORT, 9600, timeout=1)
                time.sleep(2)
                arduino.reset_input_buffer()
                arduino.reset_output_buffer()
                self._sync_controller(arduino, attempts=10, timeout_s=2.0)
                return arduino
            except Exception as exc:
                last_error = exc
                self.controller.log_event(
                    f"Belt feeder controller open failed on attempt {attempt}/{session_attempts}: {exc}"
                )
                if arduino is not None:
                    try:
                        arduino.close()
                    except Exception:
                        pass
                if self.stop_event.is_set() or self.parent_stop_event.is_set():
                    break
                time.sleep(0.8)
        raise RuntimeError(f"Unable to connect belt feeder controller: {last_error}")

    def _reconnect_controller_session(self, serial_module, arduino, accel, restart_stage):
        if arduino is not None:
            try:
                arduino.close()
            except Exception:
                pass
        self.controller._update_state(
            belt_running=False,
            belt_status="recovering",
            belt_error=None,
            message="Reconnecting belt feeder controller after a missed serial acknowledgement",
        )
        new_arduino = self._open_controller_session(serial_module)
        if restart_stage:
            self._start_staging_run(new_arduino, int(accel))
        return new_arduino

    def _start_staging_run(self, arduino, accel):
        self._send_and_wait(arduino, f"SPEED {BELT_STAGE_SPEED}", {"OK", "ERR"}, attempts=6)
        self._send_and_wait(arduino, f"ACCEL {int(accel)}", {"OK", "ERR"}, attempts=6)
        self._send_and_wait(arduino, f"RUN {BELT_STAGE_SPEED}", {"OK", "ERR"}, attempts=6)
        self.controller._update_state(
            belt_running=True,
            belt_status="staging",
            belt_mode="continuous",
            belt_speed=BELT_STAGE_SPEED,
            belt_accel=int(accel),
            belt_piece_ready=False,
            belt_ready_confirmed=False,
            belt_error=None,
            message="Feeding slowly toward the sensor to stage a red piece",
        )

    def run(self):
        arduino = None
        sensor = None
        stage_running = False
        detect_streak = 0
        pending_launch = None
        piece_staged = False
        try:
            import serial
            from FullSubsystems.belt import open_belt_tcs34725

            state = self.controller.get_state()
            sensor = open_belt_tcs34725(
                integration_time_ms=int(state["belt_detect_integration_ms"]),
                gain=4,
            )

            with self.controller._arduino_lock:
                arduino = self._open_controller_session(serial)
                self._start_staging_run(arduino, int(state["belt_accel"]))
                stage_running = True

                while not self.stop_event.is_set() and not self.parent_stop_event.is_set():
                    while True:
                        try:
                            command = self.commands.get_nowait()
                        except queue.Empty:
                            break
                        command_type = command["type"]
                        if command_type == "stop":
                            self.stop_event.set()
                            break
                        if command_type == "pause":
                            self._paused = True
                            if stage_running:
                                try:
                                    self._send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0, attempts=2)
                                    stage_running = False
                                except TimeoutError:
                                    arduino = self._reconnect_controller_session(
                                        serial,
                                        arduino,
                                        self.controller.get_state()["belt_accel"],
                                        restart_stage=False,
                                    )
                                    stage_running = False
                            self.controller._update_state(
                                belt_running=False,
                                belt_status="paused",
                                belt_mode="continuous",
                                message="Game paused; belt staging stopped",
                            )
                        elif command_type == "resume":
                            self._paused = False
                        elif command_type == "launch":
                            pending_launch = command
                            self.controller._update_state(
                                message="Launch requested; waiting for staged red piece",
                            )
                        elif command_type == "confirm_ready":
                            self._ready_confirmed = True
                            self.controller._update_state(
                                belt_ready_confirmed=True,
                                message="Confirmed staged belt piece",
                            )
                        elif command_type == "reject_ready":
                            self._ready_confirmed = False
                            piece_staged = False
                            detect_streak = 0
                            self.controller._update_state(
                                belt_piece_ready=False,
                                belt_ready_confirmed=False,
                                message="Rejected staged belt piece; resuming slow feed",
                            )
                            if not stage_running:
                                try:
                                    self._start_staging_run(arduino, int(self.controller.get_state()["belt_accel"]))
                                except TimeoutError:
                                    arduino = self._reconnect_controller_session(
                                        serial,
                                        arduino,
                                        self.controller.get_state()["belt_accel"],
                                        restart_stage=True,
                                    )
                                stage_running = True

                    if self.stop_event.is_set() or self.parent_stop_event.is_set():
                        break
                    if self._paused:
                        time.sleep(0.05)
                        continue

                    if piece_staged and not self._ready_confirmed:
                        self.controller._update_state(
                            belt_running=False,
                            belt_status="ready",
                            belt_mode="continuous",
                            belt_speed=BELT_STAGE_SPEED,
                            belt_piece_ready=True,
                            belt_ready_confirmed=False,
                            message=(
                                "Launch waiting for staged-piece confirmation."
                                if pending_launch is not None
                                else "Red piece staged at sensor. Confirm it or reject it as a false positive."
                            ),
                        )
                        time.sleep(0.02)
                        continue

                    if piece_staged and pending_launch is not None and self._ready_confirmed:
                        launch_speed = int(pending_launch["launch_speed"])
                        launch_accel = int(pending_launch["launch_accel"])
                        launch_steps = int(pending_launch["launch_steps"])
                        try:
                            self._send_and_wait(arduino, f"SPEED {launch_speed}", {"OK", "ERR"})
                            self._send_and_wait(arduino, f"ACCEL {launch_accel}", {"OK", "ERR"})
                        except TimeoutError:
                            arduino = self._reconnect_controller_session(
                                serial,
                                arduino,
                                launch_accel,
                                restart_stage=False,
                            )
                            self._send_and_wait(arduino, f"SPEED {launch_speed}", {"OK", "ERR"})
                            self._send_and_wait(arduino, f"ACCEL {launch_accel}", {"OK", "ERR"})
                        self.controller._update_state(
                            belt_running=True,
                            belt_status="launching",
                            belt_mode="steps",
                            belt_speed=launch_speed,
                            belt_accel=launch_accel,
                            belt_steps=launch_steps,
                            belt_piece_ready=False,
                            belt_ready_confirmed=True,
                            message=(
                                f"Launching red piece at {launch_speed} speed, {launch_accel} accel, "
                                f"{launch_steps} steps"
                            ),
                        )
                        try:
                            self._send_and_wait(arduino, f"RUNSTEPS {launch_steps}", {"DONE"}, timeout_s=12.0)
                        except TimeoutError:
                            arduino = self._reconnect_controller_session(
                                serial,
                                arduino,
                                self.controller.get_state()["belt_accel"],
                                restart_stage=False,
                            )
                            raise RuntimeError("Launch command lost contact with the controller; restage the red piece and try again.")
                        self.controller._update_state(
                            belt_running=False,
                            belt_status="completed",
                            belt_mode="steps",
                            belt_speed=launch_speed,
                            belt_accel=launch_accel,
                            belt_steps=launch_steps,
                            message=f"Staged red piece launched {launch_steps} steps at speed {launch_speed}",
                        )
                        pending_launch = None
                        piece_staged = False
                        self._ready_confirmed = False
                        detect_streak = 0
                        self._launch_error = None
                        self._launch_done.set()
                        time.sleep(0.02)
                        continue

                    state = self.controller.get_state()
                    sensor.integration_time = int(state["belt_detect_integration_ms"])
                    clear_thresh = float(state["belt_clear_thresh"])
                    detect_mode = state["belt_detect_mode"]
                    detect_samples = int(state["belt_detect_samples"])
                    detect_streak_target = int(state["belt_detect_streak"])

                    sample = self.controller._read_belt_color_sample(
                        sensor,
                        count=detect_samples,
                        delay_s=BELT_DETECT_SAMPLE_DELAY_S,
                    )
                    clear_value = sample["clear"]
                    covered = (
                        clear_value <= clear_thresh
                        if detect_mode == "below"
                        else clear_value >= clear_thresh
                    )
                    if covered:
                        detect_streak += 1
                    else:
                        detect_streak = 0

                    if detect_streak >= detect_streak_target:
                        if stage_running:
                            try:
                                self._send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0, attempts=2)
                                stage_running = False
                            except TimeoutError:
                                arduino = self._reconnect_controller_session(
                                    serial,
                                    arduino,
                                    state["belt_accel"],
                                    restart_stage=False,
                                )
                                stage_running = False
                        piece_staged = True
                        self._ready_confirmed = False
                        self.controller._update_state(
                            belt_piece_ready=True,
                            belt_ready_confirmed=False,
                        )
                        time.sleep(0.02)
                        continue

                    if not stage_running:
                        try:
                            self._start_staging_run(arduino, int(state["belt_accel"]))
                        except TimeoutError:
                            arduino = self._reconnect_controller_session(
                                serial,
                                arduino,
                                state["belt_accel"],
                                restart_stage=True,
                            )
                        stage_running = True
                    else:
                        self.controller._update_state(
                            belt_running=True,
                            belt_status="staging",
                            belt_mode="continuous",
                            belt_speed=BELT_STAGE_SPEED,
                            belt_accel=int(state["belt_accel"]),
                            belt_piece_ready=False,
                            belt_ready_confirmed=False,
                            belt_error=None,
                            message=(
                                "No staged red piece yet; feeding slowly toward the sensor"
                                if pending_launch is None
                                else "Launch pending; feeding slowly until a red piece reaches the sensor"
                            ),
                        )
        except Exception as exc:
            self._launch_error = str(exc)
            self._launch_done.set()
            self.controller._update_state(
                belt_running=False,
                belt_status="error",
                belt_piece_ready=False,
                belt_ready_confirmed=False,
                belt_error=str(exc),
                message="Game belt feeder failed",
                error=str(exc),
            )
        finally:
            if arduino is not None:
                try:
                    self._send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0, attempts=1)
                except Exception:
                    pass
                try:
                    arduino.close()
                except Exception:
                    pass


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
                if label == "a":
                    move_servo(pca, SERVO_CHANNEL, LEFT_PICKUP, max_angle=MAX_ANGLE, offset=OFFSET)
                    time.sleep(0.18)
                    move_servo(pca, SERVO_CHANNEL, RIGHT_PICKUP, max_angle=MAX_ANGLE, offset=OFFSET)
                    time.sleep(0.18)
                    move_servo(pca, SERVO_CHANNEL, DETECT, max_angle=MAX_ANGLE, offset=OFFSET)
                    time.sleep(DETECT_SETTLE)
                    self.controller._update_state(
                        sorter_calibration_running=True,
                        sorter_calibration_prompt=(
                            "Agitated the sorter cam. Label the current piece as red, yellow, none, or finish calibration."
                        ),
                        sorter_calibration_sample=sample,
                        sorter_calibration_counts=counts,
                        message="Sorter calibration agitated the cam",
                        error=None,
                    )
                    continue
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

            if self.stop_event.is_set():
                self.controller._update_state(
                    sorter_calibration_running=False,
                    sorter_calibration_prompt="Sorter calibration stopped.",
                    sorter_calibration_sample=None,
                    message="Sorter calibration stopped",
                    error=None,
                    sorting_enabled=False,
                    sorter_running=False,
                )
                return

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
        belt_stopped_cleanly = False
        try:
            import serial

            with self.controller._arduino_lock:
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
                    self._send_and_wait(arduino, f"RUNSTEPS {self.steps}", {"DONE"}, timeout_s=10.0)
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
                    belt_stopped_cleanly = True
                    self.controller._update_state(
                        belt_running=False,
                        belt_status="stopped",
                        belt_error=None,
                        message="Belt stopped",
                    )
        except Exception as exc:
            if str(exc) == "Belt stop requested":
                belt_stopped_cleanly = True
                self.controller._update_state(
                    belt_running=False,
                    belt_status="stopped",
                    belt_error=None,
                    message="Belt stopped",
                )
                return
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
                if belt_stopped_cleanly:
                    self.controller._belt_stop_event = None
            if arduino is not None:
                try:
                    arduino.close()
                except Exception:
                    pass


class BeltCalibrationTestWorker:
    PORT = "/dev/serial0"

    def __init__(self, controller, stop_event, commands):
        self.controller = controller
        self.stop_event = stop_event
        self.commands = commands

    def _wait_for(self, arduino, targets, timeout_s=5.0):
        deadline = time.time() + timeout_s
        while True:
            if self.stop_event.is_set():
                raise RuntimeError("Belt calibration test stop requested")
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

    def _wait_for_continue(self):
        while not self.stop_event.is_set():
            try:
                command = self.commands.get(timeout=0.1)
            except queue.Empty:
                continue
            if command["type"] == "continue":
                return True
            if command["type"] == "stop":
                self.stop_event.set()
                return False
        return False

    def run(self):
        arduino = None
        sensor = None
        servo_pca = None
        active = False
        try:
            import board
            import busio
            import serial
            from adafruit_pca9685 import PCA9685

            from FullSubsystems.belt import open_belt_tcs34725

            i2c_pca = busio.I2C(board.SCL, board.SDA)
            servo_pca = PCA9685(i2c_pca)
            servo_pca.frequency = 50
            move_game_servo(servo_pca, 0, DROP_SERVO_ANGLE)

            state = self.controller.get_state()
            speed = int(state["belt_speed"])
            accel = int(state["belt_accel"])
            clear_thresh = float(state["belt_clear_thresh"])
            detect_mode = state["belt_detect_mode"]
            post_detect_delay_ms = int(state["belt_post_detect_delay_ms"])
            detect_integration_ms = int(state["belt_detect_integration_ms"])
            detect_samples = int(state["belt_detect_samples"])
            detect_streak_target = int(state["belt_detect_streak"])

            sensor = open_belt_tcs34725(integration_time_ms=detect_integration_ms, gain=4)

            with self.controller._arduino_lock:
                arduino = serial.Serial(self.PORT, 9600, timeout=1)
                time.sleep(2)
                arduino.reset_input_buffer()
                arduino.reset_output_buffer()

                self._sync_controller(arduino)
                self._send_and_wait(arduino, f"SPEED {speed}", {"OK", "ERR"})
                self._send_and_wait(arduino, f"ACCEL {accel}", {"OK", "ERR"})

                while not self.stop_event.is_set():
                    detect_streak = 0
                    active = True
                    self._send_and_wait(arduino, f"RUN {speed}", {"OK", "ERR"})
                    self.controller._update_state(
                        belt_test_running=True,
                        belt_test_waiting_continue=False,
                        belt_test_prompt=(
                            f"Running test at speed {speed}. Waiting for a piece to cover the belt sensor."
                        ),
                        belt_running=True,
                        belt_status="test-running",
                        belt_mode="continuous",
                        belt_speed=speed,
                        belt_accel=accel,
                        belt_error=None,
                        message="Belt calibration test running",
                    )

                    while not self.stop_event.is_set():
                        sample = self.controller._read_belt_color_sample(
                            sensor,
                            count=detect_samples,
                            delay_s=BELT_DETECT_SAMPLE_DELAY_S,
                        )
                        clear_value = sample["clear"]
                        covered = (
                            clear_value <= clear_thresh
                            if detect_mode == "below"
                            else clear_value >= clear_thresh
                        )
                        if covered:
                            detect_streak += 1
                        else:
                            detect_streak = 0

                        self.controller._update_state(
                            belt_calibration_last_sample=sample,
                            belt_running=True,
                            belt_status="test-running",
                            message=(
                                f"Test running (clear={clear_value:.1f}, threshold={clear_thresh:.1f}, "
                                f"mode={detect_mode}, int={detect_integration_ms}ms, "
                                f"samples={detect_samples}, streak={detect_streak_target})"
                            ),
                        )

                        if detect_streak >= detect_streak_target:
                            self.controller._update_state(
                                belt_test_prompt=(
                                    f"Detected a piece at clear={clear_value:.1f}. "
                                    f"Continuing for {post_detect_delay_ms} ms before stopping."
                                ),
                                message="Belt test detected a piece; coasting before stop",
                            )
                            time.sleep(post_detect_delay_ms / 1000.0)
                            self._send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0)
                            active = False
                            self.controller._update_state(
                                belt_test_running=True,
                                belt_test_waiting_continue=True,
                                belt_test_prompt=(
                                    f"Detected a piece at clear={clear_value:.1f} and stopped "
                                    f"{post_detect_delay_ms} ms later. Press Continue to run the next piece."
                                ),
                                belt_running=False,
                                belt_status="test-paused",
                                belt_mode="continuous",
                                message=f"Belt test paused {post_detect_delay_ms} ms after detection",
                            )
                            if not self._wait_for_continue():
                                return
                            self.controller._update_state(
                                belt_test_waiting_continue=False,
                                belt_test_prompt="Continuing belt calibration test.",
                                message="Continuing belt calibration test",
                            )
                            break
        except Exception as exc:
            self.controller._update_state(
                belt_test_running=False,
                belt_test_waiting_continue=False,
                belt_test_prompt=f"Belt calibration test failed: {exc}",
                belt_running=False,
                belt_status="error",
                belt_error=str(exc),
                message="Belt calibration test failed",
                error=str(exc),
            )
        finally:
            if active and arduino is not None:
                try:
                    self._send_and_wait(arduino, "STOP", {"OK"}, timeout_s=2.0, attempts=1)
                except Exception:
                    pass
            if servo_pca is not None:
                try:
                    move_game_servo(servo_pca, 0, 0)
                except Exception:
                    pass
                servo_pca.deinit()
            if arduino is not None:
                try:
                    arduino.close()
                except Exception:
                    pass
            with self.controller._lock:
                if self.controller._belt_test_thread is threading.current_thread():
                    self.controller._belt_test_thread = None
                self.controller._belt_test_stop_event = None
                self.controller._belt_test_commands = None
            if self.controller.get_state()["belt_status"] != "error":
                self.controller._update_state(
                    belt_test_running=False,
                    belt_test_waiting_continue=False,
                    belt_test_prompt="Belt calibration test idle.",
                    belt_running=False,
                    belt_status="idle",
                    belt_error=None,
                )


class GateWorker:
    PORT = GATE_PORT

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
                raise RuntimeError("Gate stop requested")
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
        gate_stopped_cleanly = False
        try:
            import serial

            with self.controller._arduino_lock:
                arduino = serial.Serial(self.PORT, 9600, timeout=1)
                time.sleep(2)
                arduino.reset_input_buffer()
                arduino.reset_output_buffer()

                self._sync_controller(arduino)
                self._send_and_wait(arduino, f"GATE SPEED {self.speed}", {"OK", "ERR"})
                self._send_and_wait(arduino, f"GATE ACCEL {self.accel}", {"OK", "ERR"})

                if self.steps is not None:
                    self.controller._update_state(
                        gate_status="running",
                        gate_mode="steps",
                        message=f"Running gate for {self.steps} steps",
                    )
                    self._send_and_wait(arduino, f"GATE STEPS {self.steps}", {"DONE"}, timeout_s=12.0)
                    with self.controller._lock:
                        if self.steps > 0:
                            self.controller._gate_is_out = True
                        elif self.steps < 0:
                            self.controller._gate_is_out = False
                    self.controller._update_state(
                        gate_running=False,
                        gate_status="completed",
                        message=f"Gate step run completed ({self.steps} steps)",
                    )
                else:
                    self._send_and_wait(arduino, f"GATE RUN {self.speed}", {"OK", "ERR"})
                    self.controller._update_state(
                        gate_running=True,
                        gate_status="running",
                        gate_mode="continuous",
                        message=f"Gate running continuously at {self.speed} steps/sec",
                    )
                    while not self.stop_event.is_set():
                        time.sleep(0.1)
                    self._send_and_wait(arduino, "GATE STOP", {"OK"}, timeout_s=2.0)
                    gate_stopped_cleanly = True
                    self.controller._update_state(
                        gate_running=False,
                        gate_status="stopped",
                        gate_error=None,
                        message="Gate stepper stopped",
                    )
        except Exception as exc:
            if str(exc) == "Gate stop requested":
                gate_stopped_cleanly = True
                self.controller._update_state(
                    gate_running=False,
                    gate_status="stopped",
                    gate_error=None,
                    message="Gate stepper stopped",
                )
                return
            self.controller._update_state(
                gate_running=False,
                gate_status="error",
                gate_error=str(exc),
                message="Gate control failed",
                error=str(exc),
            )
        finally:
            with self.controller._lock:
                if self.controller._gate_thread is threading.current_thread():
                    self.controller._gate_thread = None
                if gate_stopped_cleanly:
                    self.controller._gate_stop_event = None
            if arduino is not None:
                try:
                    arduino.close()
                except Exception:
                    pass
