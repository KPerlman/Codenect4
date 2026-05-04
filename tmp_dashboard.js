
    let latestState = null;
    let healthState = null;

    async function api(path, method = "GET", body = null) {
      if (typeof fetch === "function") {
        const res = await fetch(path, {
          method,
          headers: { "Content-Type": "application/json" },
          body: body ? JSON.stringify(body) : null
        });
        return res.json();
      }

      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(method, path, true);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.onreadystatechange = () => {
          if (xhr.readyState !== 4) return;
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText));
            } catch (err) {
              reject(err);
            }
          } else {
            reject(new Error(`HTTP ${xhr.status}`));
          }
        };
        xhr.onerror = () => reject(new Error("XHR request failed"));
        xhr.send(body ? JSON.stringify(body) : null);
      });
    }

    async function startGame() {
      await syncBeltSettings();
      await api("/api/game/start", "POST", { device: "/dev/video0", width: 640, height: 480, depth: 5, state_streak: 3 });
      await refresh();
    }

    async function handlePrimaryGameAction() {
      if (latestState && latestState.game_running && latestState.game_status !== "finished" && latestState.game_status !== "error") {
        await togglePauseGame();
        return;
      }
      await startGame();
    }

    async function togglePauseGame() {
      await api("/api/game/pause-toggle", "POST");
      await refresh();
    }

    async function resetGame() {
      await syncBeltSettings();
      await api("/api/game/reset", "POST", { device: "/dev/video0", width: 640, height: 480, depth: 5, state_streak: 3 });
      await refresh();
    }

    async function rebootRuntime() {
      await api("/api/runtime/reboot", "POST");
      await refresh();
      await refreshHealth();
    }

    async function copyRuntimeLog() {
      if (!latestState || !Array.isArray(latestState.runtime_log)) return;
      const payload = latestState.runtime_log.join("\n");
      try {
        await navigator.clipboard.writeText(payload);
      } catch (err) {
        console.warn("Clipboard copy failed", err);
      }
    }

    async function enableSorting() {
      await api("/api/sorting/enable", "POST");
      await refresh();
    }

    async function disableSorting() {
      await api("/api/sorting/disable", "POST");
      await refresh();
    }

    async function startSorterCalibration() {
      await api("/api/sorting/calibration/start", "POST");
      await refresh();
    }

    async function labelSorterCalibration(label) {
      await api("/api/sorting/calibration/label", "POST", { label });
      await refresh();
    }

    async function zeroServos() {
      await api("/api/servos/zero", "POST");
      await refresh();
    }

    async function syncBeltSettings() {
      const speed = parseInt(document.getElementById("beltSpeed").value || "600", 10);
      const accel = parseInt(document.getElementById("beltAccel").value || "400", 10);
      const stepsValue = document.getElementById("beltSteps").value.trim();
      const clearThreshValue = document.getElementById("beltClearThresh").value.trim();
      const postDetectValue = document.getElementById("beltPostDetectDelayMs").value.trim();
      const detectIntegrationValue = document.getElementById("beltDetectIntegrationMs").value.trim();
      const detectSamplesValue = document.getElementById("beltDetectSamples").value.trim();
      const detectStreakValue = document.getElementById("beltDetectStreak").value.trim();
      const launchSpeedValue = document.getElementById("beltLaunchSpeed").value.trim();
      const launchAccelValue = document.getElementById("beltLaunchAccel").value.trim();
      const launchStepsValue = document.getElementById("beltLaunchSteps").value.trim();
      const game_belt_enabled = !(latestState && latestState.game_belt_enabled === false);
      const steps = stepsValue === "" ? null : parseInt(stepsValue, 10);
      const clear_thresh = clearThreshValue === "" ? null : parseFloat(clearThreshValue);
      const post_detect_delay_ms = postDetectValue === "" ? null : parseInt(postDetectValue, 10);
      const detect_integration_ms = detectIntegrationValue === "" ? null : parseInt(detectIntegrationValue, 10);
      const detect_samples = detectSamplesValue === "" ? null : parseInt(detectSamplesValue, 10);
      const detect_streak = detectStreakValue === "" ? null : parseInt(detectStreakValue, 10);
      const launch_speed = launchSpeedValue === "" ? null : parseInt(launchSpeedValue, 10);
      const launch_accel = launchAccelValue === "" ? null : parseInt(launchAccelValue, 10);
      const launch_steps = launchStepsValue === "" ? null : parseInt(launchStepsValue, 10);
      await api("/api/belt/settings", "POST", {
        speed, accel, steps, launch_speed, launch_accel, launch_steps, clear_thresh, post_detect_delay_ms, detect_integration_ms, detect_samples, detect_streak, game_belt_enabled
      });
    }

    async function toggleGameBeltMode() {
      const nextEnabled = !(latestState && latestState.game_belt_enabled !== false);
      const speed = parseInt(document.getElementById("beltSpeed").value || "600", 10);
      const accel = parseInt(document.getElementById("beltAccel").value || "400", 10);
      const stepsValue = document.getElementById("beltSteps").value.trim();
      const clearThreshValue = document.getElementById("beltClearThresh").value.trim();
      const postDetectValue = document.getElementById("beltPostDetectDelayMs").value.trim();
      const detectIntegrationValue = document.getElementById("beltDetectIntegrationMs").value.trim();
      const detectSamplesValue = document.getElementById("beltDetectSamples").value.trim();
      const detectStreakValue = document.getElementById("beltDetectStreak").value.trim();
      const launchSpeedValue = document.getElementById("beltLaunchSpeed").value.trim();
      const launchAccelValue = document.getElementById("beltLaunchAccel").value.trim();
      const launchStepsValue = document.getElementById("beltLaunchSteps").value.trim();
      const steps = stepsValue === "" ? null : parseInt(stepsValue, 10);
      const clear_thresh = clearThreshValue === "" ? null : parseFloat(clearThreshValue);
      const post_detect_delay_ms = postDetectValue === "" ? null : parseInt(postDetectValue, 10);
      const detect_integration_ms = detectIntegrationValue === "" ? null : parseInt(detectIntegrationValue, 10);
      const detect_samples = detectSamplesValue === "" ? null : parseInt(detectSamplesValue, 10);
      const detect_streak = detectStreakValue === "" ? null : parseInt(detectStreakValue, 10);
      const launch_speed = launchSpeedValue === "" ? null : parseInt(launchSpeedValue, 10);
      const launch_accel = launchAccelValue === "" ? null : parseInt(launchAccelValue, 10);
      const launch_steps = launchStepsValue === "" ? null : parseInt(launchStepsValue, 10);
      await api("/api/belt/settings", "POST", {
        speed,
        accel,
        steps,
        launch_speed,
        launch_accel,
        launch_steps,
        clear_thresh,
        post_detect_delay_ms,
        detect_integration_ms,
        detect_samples,
        detect_streak,
        game_belt_enabled: nextEnabled,
      });
      await refresh();
    }

    async function toggleBelt() {
      await syncBeltSettings();
      if (latestState && latestState.belt_running) {
        await api("/api/belt/stop", "POST");
        await refresh();
        return;
      }
      const speed = parseInt(document.getElementById("beltSpeed").value || "600", 10);
      const accel = parseInt(document.getElementById("beltAccel").value || "400", 10);
      const stepsValue = document.getElementById("beltSteps").value.trim();
      const steps = stepsValue === "" ? null : parseInt(stepsValue, 10);
      await api("/api/belt/start", "POST", { speed, accel, steps });
      await refresh();
    }

    async function startBeltCalibration() {
      await syncBeltSettings();
      await api("/api/belt/calibration/start", "POST");
      await refresh();
    }

    async function beltCalibrationAction(action) {
      await api("/api/belt/calibration/action", "POST", { action });
      await refresh();
    }

    async function toggleBeltTest() {
      await syncBeltSettings();
      if (latestState && latestState.belt_test_running) {
        await api("/api/belt/test/stop", "POST");
      } else {
        await api("/api/belt/test/start", "POST");
      }
      await refresh();
    }

    async function continueBeltTest() {
      await api("/api/belt/test/continue", "POST");
      await refresh();
    }

    async function confirmBeltReady(accept) {
      await api("/api/belt/ready-confirm", "POST", { accept });
      await refresh();
    }

    async function toggleGate() {
      if (latestState && latestState.gate_running) {
        await api("/api/gate/stop", "POST");
        await refresh();
        return;
      }
      const speed = parseInt(document.getElementById("gateSpeed").value || "600", 10);
      const accel = parseInt(document.getElementById("gateAccel").value || "400", 10);
      const stepsValue = document.getElementById("gateSteps").value.trim();
      const steps = stepsValue === "" ? null : parseInt(stepsValue, 10);
      await api("/api/gate/start", "POST", { speed, accel, steps });
      await refresh();
    }

    async function confirmYellow(accept) {
      await api("/api/game/yellow-confirm", "POST", { accept });
      await refresh();
    }

    async function confirmRed() {
      await api("/api/game/red-confirm", "POST");
      await refresh();
    }

    async function manualYellowMove(column) {
      await api("/api/game/manual-human-move", "POST", { column });
      await refresh();
    }

    async function removeBoardPiece(row, column) {
      await api("/api/game/remove-piece", "POST", { row, column });
      await refresh();
    }

    function getPendingYellowCells(state) {
      if (!state || state.awaiting_confirmation !== "yellow" || !state.current_board || !state.confirmed_board) {
        return [];
      }
      const pending = [];
      for (let r = 0; r < state.current_board.length; r++) {
        for (let c = 0; c < state.current_board[r].length; c++) {
          if (state.current_board[r][c] === 2 && state.confirmed_board[r][c] !== 2) {
            pending.push({ row: r, col: c });
          }
        }
      }
      return pending;
    }

    async function handleBoardClick(visibleColumn, row, isPendingCell, isConfirmedOccupied) {
      if (!latestState) return;
      if (
        latestState.game_status === "waiting_human_move" ||
        latestState.turn_state === "human_turn"
      ) {
        if (isConfirmedOccupied) {
          await removeBoardPiece(row, visibleColumn);
          return;
        }
        await manualYellowMove(visibleColumn);
        return;
      }
      if (latestState.awaiting_confirmation === "yellow") {
        if (isPendingCell) {
          await confirmYellow(true);
          return;
        }
        if (isConfirmedOccupied) {
          await removeBoardPiece(row, visibleColumn);
          return;
        }
        await api("/api/game/yellow-confirm", "POST", { accept: false, column: visibleColumn });
        await refresh();
        return;
      }
      if (
        latestState.awaiting_confirmation === "red" &&
        latestState.suggested_red_column !== null &&
        visibleColumn === latestState.suggested_red_column
      ) {
        await confirmRed();
        return;
      }
      if (isConfirmedOccupied) {
        await removeBoardPiece(row, visibleColumn);
      }
    }

    function normalizeBoard(board) {
      if (!Array.isArray(board) || board.length !== 6) {
        return Array.from({ length: 6 }, () => Array(7).fill(0));
      }
      return board.map((row) => {
        if (!Array.isArray(row) || row.length !== 7) {
          return Array(7).fill(0);
        }
        return row.map((cell) => (cell === 1 || cell === 2 ? cell : 0));
      });
    }

    function renderBoard(board) {
      const root = document.getElementById("board");
      if (!root) return;
      root.innerHTML = "";
      const safeBoard = normalizeBoard(board);
      const mirrored = safeBoard.map(row => [...row].reverse());
      const pendingCells = getPendingYellowCells(latestState);
      const pendingKeys = new Set(pendingCells.map(cell => `${cell.row}:${cell.col}`));
      for (let rowIdx = 0; rowIdx < mirrored.length; rowIdx++) {
        const row = mirrored[rowIdx];
        for (let colIdx = 0; colIdx < row.length; colIdx++) {
          const cell = row[colIdx];
          const slot = document.createElement("div");
          slot.className = "slot";
          if (cell === 1) slot.classList.add("red");
          if (cell === 2) slot.classList.add("yellow");
          const originalCol = row.length - 1 - colIdx;
          const key = `${rowIdx}:${originalCol}`;
          const isPending = pendingKeys.has(key);
          const confirmedBoard = latestState && latestState.confirmed_board ? latestState.confirmed_board : null;
          const isConfirmedOccupied = !!(
            confirmedBoard &&
            confirmedBoard[rowIdx] &&
            confirmedBoard[rowIdx][originalCol] !== 0 &&
            !isPending
          );
          if (isPending) {
            slot.classList.remove("yellow");
            slot.classList.add("pending-yellow");
          }
          if (
            latestState &&
            (latestState.game_status === "waiting_human_move" ||
              latestState.turn_state === "human_turn")
          ) {
            slot.classList.add("clickable", "manual-yellow");
            slot.title = isConfirmedOccupied
              ? `Remove confirmed piece at row ${rowIdx}, column ${originalCol}`
              : `Register yellow in column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, rowIdx, false, isConfirmedOccupied));
          } else if (latestState && latestState.awaiting_confirmation === "yellow") {
            slot.classList.add("clickable");
            slot.title = isPending
              ? `Confirm detected yellow in column ${originalCol}`
              : isConfirmedOccupied
                ? `Remove confirmed piece at row ${rowIdx}, column ${originalCol}`
                : `Override to column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, rowIdx, isPending, isConfirmedOccupied));
          } else if (
            latestState &&
            latestState.awaiting_confirmation === "red" &&
            latestState.suggested_red_column !== null &&
            originalCol === latestState.suggested_red_column
          ) {
            slot.classList.add("clickable");
            slot.title = `Confirm red placement in column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, rowIdx, false, false));
          } else if (isConfirmedOccupied) {
            slot.classList.add("clickable");
            slot.title = `Remove confirmed piece at row ${rowIdx}, column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, rowIdx, false, true));
          }
          root.appendChild(slot);
        }
      }
    }

    function bannerConfig(state) {
      if (state.sorter_calibration_running) {
        return {
          className: "banner waiting",
          title: "Sorter calibration active",
          text: state.sorter_calibration_prompt || "Label the current sorter sample from the calibration panel.",
        };
      }
      if (state.awaiting_confirmation === "yellow") {
        return {
          className: "banner waiting",
          title: `Yellow move detected in column ${state.detected_yellow_column ?? "-"}`,
          text: state.prompt || "Confirm the detected yellow move or correct it.",
        };
      }
      if (state.awaiting_confirmation === "red") {
        return {
          className: "banner waiting",
          title: `Place red in column ${state.suggested_red_column ?? "-"}`,
          text: state.prompt || "Drop the red piece on the real board and let vision confirm it.",
        };
      }
      if (state.game_status === "ready_for_launch") {
        return {
          className: "banner waiting",
          title: `Ready for launch: column ${state.suggested_red_column ?? "-"}`,
          text: state.prompt || "The robot has chosen a column and is preparing the red launch.",
        };
      }
      if (state.game_status === "thinking") {
        return {
          className: "banner thinking",
          title: "Computer is thinking",
          text: "",
        };
      }
      if (state.game_status === "paused") {
        return {
          className: "banner waiting",
          title: "Game paused",
          text: state.message || "Resume when you're ready.",
        };
      }
      if (state.game_status === "waiting_human_move") {
        return {
          className: "banner ready",
          title: "Player turn",
          text: state.prompt || "Drop a yellow piece and hold the board steady.",
        };
      }
      if (state.game_status === "calibrating") {
        return {
          className: "banner",
          title: "Calibrating board",
          text: "Keep the board visible and empty for a moment.",
        };
      }
      if (state.game_status === "starting") {
        return {
          className: "banner",
          title: "Starting game loop",
          text: "Opening the camera, bringing the board online, and preparing the runtime.",
        };
      }
      if (state.game_status === "finished") {
        return {
          className: "banner ready",
          title: state.winner === 1 ? "Red wins" : state.winner === 2 ? "Yellow wins" : "Game finished",
          text: state.message || "Reset when you're ready for the next round.",
        };
      }
      if (state.game_status === "error") {
        return {
          className: "banner waiting",
          title: "Something needs attention",
          text: state.error || state.message || "Check the service logs and current hardware state.",
        };
      }
      return {
        className: "banner",
        title: "Idle",
        text: state.message || "Start the game loop when you're ready.",
      };
    }

    function renderBanner(state) {
      const config = bannerConfig(state);
      const banner = document.getElementById("turnBanner");
      const title = document.getElementById("bannerTitle");
      const text = document.getElementById("bannerText");
      banner.className = config.className;
      if (state.game_status === "thinking") {
        title.innerHTML = `<span class="thinking-line">Computer is thinking<span class="loading-dots"><span></span><span></span><span></span></span></span>`;
      } else {
        title.textContent = config.title;
      }
      text.textContent = config.text;
      text.style.display = config.text ? "block" : "none";
    }

    function winnerLabel(value) {
      if (value === 1) return "red";
      if (value === 2) return "yellow";
      return "none";
    }

    function renderMeta(state) {
      document.getElementById("metaStatus").textContent = state.game_status;
      document.getElementById("metaTracker").textContent = state.tracker_calibrated ? "calibrated" : "calibrating";
      document.getElementById("metaCamera").textContent = state.camera_source || "n/a";
      document.getElementById("metaRed").textContent =
        state.suggested_red_column !== null ? state.suggested_red_column : "-";
    }

    function renderStateBlocks(state) {
      document.getElementById("stateGameRunning").textContent = state.game_running ? "yes" : "no";
      document.getElementById("stateGamePhase").textContent = state.game_phase || "idle";
      document.getElementById("stateTurnState").textContent = state.turn_state || "idle";
      document.getElementById("stateWinner").textContent = winnerLabel(state.winner);

      document.getElementById("stateSortingEnabled").textContent = state.sorting_enabled ? "yes" : "no";
      document.getElementById("stateSorterRunning").textContent = state.sorter_running ? "running" : "off";
      document.getElementById("stateSorterCalibration").textContent =
        state.sorter_calibration_running ? "running" : "idle";
      document.getElementById("stateTrackerActive").textContent = state.tracker_active ? "yes" : "no";
      document.getElementById("stateTrackerCalibrated").textContent = state.tracker_calibrated ? "yes" : "no";

      document.getElementById("stateYellowCount").textContent = state.confirmed_yellow_count ?? 0;
      document.getElementById("stateRedCount").textContent = state.confirmed_red_count ?? 0;
      document.getElementById("statePendingYellow").textContent = state.pending_yellow_count ?? 0;
      document.getElementById("stateAwaiting").textContent = state.awaiting_confirmation || "none";

      document.getElementById("stateCameraSource").textContent = state.camera_source || "n/a";
      document.getElementById("stateYellowCol").textContent =
        state.detected_yellow_column !== null ? state.detected_yellow_column : "-";
      document.getElementById("stateRedCol").textContent =
        state.suggested_red_column !== null ? state.suggested_red_column : "-";
      document.getElementById("stateUpdated").textContent =
        state.updated_at ? new Date(state.updated_at * 1000).toLocaleTimeString() : "-";
    }

    function renderBeltPanel(state) {
      const status = document.getElementById("beltStatusText");
      const button = document.getElementById("beltActionButton");
      const modeButton = document.getElementById("gameBeltModeButton");
      const testButton = document.getElementById("beltTestButton");
      const continueButton = document.getElementById("beltTestContinueButton");
      const readyConfirmButton = document.getElementById("beltReadyConfirmButton");
      const readyRejectButton = document.getElementById("beltReadyRejectButton");
      if (!status || !button) return;

      const clearInput = document.getElementById("beltClearThresh");
      const postDetectInput = document.getElementById("beltPostDetectDelayMs");
      const detectIntegrationInput = document.getElementById("beltDetectIntegrationMs");
      const detectSamplesInput = document.getElementById("beltDetectSamples");
      const detectStreakInput = document.getElementById("beltDetectStreak");
      const launchSpeedInput = document.getElementById("beltLaunchSpeed");
      const launchAccelInput = document.getElementById("beltLaunchAccel");
      const launchStepsInput = document.getElementById("beltLaunchSteps");
      if (clearInput && document.activeElement !== clearInput && state.belt_clear_thresh !== undefined) {
        clearInput.value = Number(state.belt_clear_thresh).toFixed(1);
      }
      if (postDetectInput && document.activeElement !== postDetectInput && state.belt_post_detect_delay_ms !== undefined) {
        postDetectInput.value = `${state.belt_post_detect_delay_ms}`;
      }
      if (detectIntegrationInput && document.activeElement !== detectIntegrationInput && state.belt_detect_integration_ms !== undefined) {
        detectIntegrationInput.value = `${state.belt_detect_integration_ms}`;
      }
      if (detectSamplesInput && document.activeElement !== detectSamplesInput && state.belt_detect_samples !== undefined) {
        detectSamplesInput.value = `${state.belt_detect_samples}`;
      }
      if (detectStreakInput && document.activeElement !== detectStreakInput && state.belt_detect_streak !== undefined) {
        detectStreakInput.value = `${state.belt_detect_streak}`;
      }
      if (launchSpeedInput && document.activeElement !== launchSpeedInput && state.belt_launch_speed !== undefined) {
        launchSpeedInput.value = `${state.belt_launch_speed}`;
      }
      if (launchAccelInput && document.activeElement !== launchAccelInput && state.belt_launch_accel !== undefined) {
        launchAccelInput.value = `${state.belt_launch_accel}`;
      }
      if (launchStepsInput && document.activeElement !== launchStepsInput && state.belt_launch_steps !== undefined) {
        launchStepsInput.value = `${state.belt_launch_steps}`;
      }
      if (modeButton) {
        const enabled = state.game_belt_enabled !== false;
        modeButton.textContent = enabled ? "Game Belt: On" : "Game Belt: Manual Drop";
        modeButton.className = enabled ? "secondary" : "warning";
      }
      if (testButton) {
        testButton.textContent = state.belt_test_running ? "Stop Belt Test" : "Test Belt Calibration";
        testButton.className = state.belt_test_running ? "danger" : "secondary";
      }
      if (continueButton) {
        continueButton.disabled = !state.belt_test_running || !state.belt_test_waiting_continue;
      }

      if (state.belt_test_running) {
        status.textContent = state.belt_test_prompt || "Belt calibration test running.";
        button.textContent = "Start Belt";
        button.className = "ok";
        button.disabled = true;
        return;
      }
      button.disabled = false;

      if (state.belt_running) {
        const modeText = state.belt_mode === "steps"
          ? `Running ${state.belt_steps ?? "-"} steps at ${state.belt_speed} / accel ${state.belt_accel}.`
          : `Running continuously at ${state.belt_speed} / accel ${state.belt_accel}.`;
        status.textContent = modeText;
        button.textContent = "Stop Belt";
        button.className = "danger";
      } else if (state.belt_status === "ready") {
        status.textContent = state.belt_ready_confirmed
          ? "Belt piece ready and confirmed for launch."
          : "Belt piece ready at the sensor. Confirm it or reject it as a false positive.";
        button.textContent = "Start Belt";
        button.className = "ok";
      } else {
        const detail = state.belt_error
          ? ` Error: ${state.belt_error}`
          : state.belt_status === "completed"
            ? " Last step run completed."
            : "";
        status.textContent = `Belt ${state.belt_status || "idle"}.${detail}`;
        button.textContent = "Start Belt";
        button.className = "ok";
      }
    }

    function renderBeltCalibration(state) {
      const card = document.getElementById("beltCalibrationCard");
      const copy = document.getElementById("beltCalibrationCopy");
      const sample = document.getElementById("beltCalibrationSample");
      const counts = document.getElementById("beltCalibrationCounts");
      const emptyBtn = document.getElementById("beltCaptureEmpty");
      const pieceBtn = document.getElementById("beltCapturePiece");
      const finishBtn = document.getElementById("beltFinishCalibration");
      const cancelBtn = document.getElementById("beltCancelCalibration");

      const active = !!state.belt_calibration_running;
      card.classList.toggle("hidden", !active);
      if (!active) {
        return;
      }

      copy.textContent = state.belt_calibration_prompt || "Capture empty and covered-piece samples.";
      if (state.belt_calibration_last_sample) {
        const s = state.belt_calibration_last_sample;
        sample.textContent = `Sample r=${s.r.toFixed(1)} g=${s.g.toFixed(1)} b=${s.b.toFixed(1)} clear=${s.clear.toFixed(1)}`;
      } else {
        sample.textContent = "No sample yet.";
      }
      const c = state.belt_calibration_counts || { empty: 0, piece: 0 };
      counts.textContent = `empty ${c.empty ?? 0} | piece ${c.piece ?? 0}`;
      emptyBtn.disabled = !active;
      pieceBtn.disabled = !active;
      finishBtn.disabled = !active;
      cancelBtn.disabled = !active;
    }

    function renderGatePanel(state) {
      const status = document.getElementById("gateStatusText");
      const button = document.getElementById("gateActionButton");
      if (!status || !button) return;

      if (state.gate_running) {
        const modeText = state.gate_mode === "steps"
          ? `Running ${state.gate_steps ?? "-"} steps at ${state.gate_speed} / accel ${state.gate_accel}.`
          : `Running continuously at ${state.gate_speed} / accel ${state.gate_accel}.`;
        status.textContent = modeText;
        button.textContent = "Stop Gate";
        button.className = "danger";
      } else {
        const detail = state.gate_error
          ? ` Error: ${state.gate_error}`
          : state.gate_status === "completed"
            ? " Last step run completed."
            : "";
        status.textContent = `Gate ${state.gate_status || "idle"}.${detail}`;
        button.textContent = "Start Gate";
        button.className = "ok";
      }
    }

    function renderSorterCalibration(state) {
      const card = document.getElementById("sorterCalibrationCard");
      const title = document.getElementById("sorterCalibrationTitle");
      const copy = document.getElementById("sorterCalibrationCopy");
      const sample = document.getElementById("sorterCalibrationSample");
      const counts = document.getElementById("sorterCalibrationCounts");
      const redBtn = document.getElementById("sorterLabelRed");
      const yellowBtn = document.getElementById("sorterLabelYellow");
      const noneBtn = document.getElementById("sorterLabelNone");
      const agitateBtn = document.getElementById("sorterLabelAgitate");
      const quitBtn = document.getElementById("sorterLabelQuit");
      const calibrationCounts = state.sorter_calibration_counts || { red: 0, yellow: 0, none: 0 };
      const active = !!state.sorter_calibration_running;

      card.classList.toggle("hidden", !active);
      title.textContent = "Calibration active";

      copy.textContent = state.sorter_calibration_prompt || "Label the current sorter sample.";

      if (state.sorter_calibration_sample) {
        const s = state.sorter_calibration_sample;
        sample.textContent = `Sample r=${s.r.toFixed(1)} g=${s.g.toFixed(1)} b=${s.b.toFixed(1)} clear=${s.clear.toFixed(1)}`;
      } else {
        sample.textContent = "No sample yet.";
      }

      counts.textContent = `red ${calibrationCounts.red ?? 0} | yellow ${calibrationCounts.yellow ?? 0} | none ${calibrationCounts.none ?? 0}`;
      redBtn.disabled = !active;
      yellowBtn.disabled = !active;
      noneBtn.disabled = !active;
      agitateBtn.disabled = !active;
      quitBtn.disabled = !active;
    }

    function renderConfirmationCards(state) {
      const yellowCard = document.getElementById("yellowCard");
      const redCard = document.getElementById("redCard");
      const yellowCopy = document.getElementById("yellowCopy");
      const redCopy = document.getElementById("redCopy");

      yellowCard.classList.toggle("hidden", state.awaiting_confirmation !== "yellow");
      redCard.classList.toggle("hidden", state.awaiting_confirmation !== "red");

      if (state.awaiting_confirmation === "yellow") {
        yellowCopy.textContent = state.prompt || "Tap the highlighted yellow slot to confirm it, or tap another slot to override it.";
      }
      if (state.awaiting_confirmation === "red") {
        redCopy.textContent = state.prompt || (
          state.game_belt_enabled === false
            ? "Manually drop the red piece at the top and confirm it here."
            : "Place the red piece and let vision confirm it automatically."
        );
      }
      if (state.awaiting_confirmation !== "yellow" && state.awaiting_confirmation !== "red") {
        yellowCopy.textContent = "Detected a yellow move. Confirm it or correct the column.";
        redCopy.textContent = state.game_belt_enabled === false
          ? "The computer has chosen a red column. Manually drop the piece at the top and confirm it here."
          : "The computer has chosen a red column. Place the piece and let vision confirm it automatically.";
      }
    }

    function renderGameControls(state) {
      const primaryButton = document.getElementById("primaryGameButton");
      const readyControls = document.getElementById("beltReadyControls");
      const readyConfirmButton = document.getElementById("beltReadyConfirmButton");
      const readyRejectButton = document.getElementById("beltReadyRejectButton");
      if (!primaryButton) return;

      const gameActive = !!state.game_running && state.game_status !== "finished" && state.game_status !== "error";
      if (gameActive) {
        if (state.game_paused) {
          primaryButton.textContent = "Resume Game";
          primaryButton.className = "ok";
        } else {
          primaryButton.textContent = "Pause Game";
          primaryButton.className = "secondary";
        }
      } else {
        primaryButton.textContent = "Start Game";
        primaryButton.className = "ok";
      }
      primaryButton.disabled = state.game_status === "starting";

      const showReadyControls = state.game_running && state.belt_status === "ready";
      if (readyControls) {
        readyControls.classList.toggle("hidden", !showReadyControls);
      }
      if (readyConfirmButton) {
        readyConfirmButton.disabled = !(showReadyControls && !state.belt_ready_confirmed);
      }
      if (readyRejectButton) {
        readyRejectButton.disabled = !showReadyControls;
      }
    }

    function renderRuntimeLog(state) {
      const logPanel = document.getElementById("runtimeLogPanel");
      if (!logPanel) return;
      const lines = Array.isArray(state.runtime_log) ? state.runtime_log : [];
      const nextText = lines.length ? lines.join("\n") : "No runtime log entries yet.";
      if (logPanel.textContent !== nextText) {
        const nearBottom = (logPanel.scrollHeight - logPanel.scrollTop - logPanel.clientHeight) < 24;
        logPanel.textContent = nextText;
        if (nearBottom) {
          logPanel.scrollTop = logPanel.scrollHeight;
        }
      }
    }

    async function refresh() {
      try {
        latestState = await api("/api/state");
        renderBanner(latestState);
        renderMeta(latestState);
        renderStateBlocks(latestState);
        renderGameControls(latestState);
        renderRuntimeLog(latestState);
        renderBeltPanel(latestState);
        renderBeltCalibration(latestState);
        renderGatePanel(latestState);
        renderSorterCalibration(latestState);
        renderConfirmationCards(latestState);
        renderBoard(latestState.current_board);
      } catch (err) {
        console.error("Dashboard refresh failed", err);
      }
    }

    async function refreshHealth() {
      try {
        healthState = await api("/health");
        document.getElementById("versionBadge").textContent =
          `service: ${healthState.service} | version: ${healthState.version}`;
      } catch (err) {
        document.getElementById("versionBadge").textContent = "service health unavailable";
      }
    }

    try {
      ["beltSpeed", "beltAccel", "beltSteps", "beltClearThresh", "beltPostDetectDelayMs", "beltDetectIntegrationMs", "beltDetectSamples", "beltDetectStreak", "beltLaunchSpeed", "beltLaunchAccel", "beltLaunchSteps"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
          el.addEventListener("change", () => {
            syncBeltSettings().catch(() => {});
          });
        }
      });

      window.addEventListener("load", () => {
        refreshHealth().catch((err) => console.error("Initial health refresh failed", err));
        refresh().catch((err) => console.error("Initial dashboard refresh failed", err));
        setInterval(() => refreshHealth().catch(() => {}), 5000);
        setInterval(() => refresh().catch(() => {}), 800);
      });
    } catch (err) {
      console.error("Dashboard bootstrap failed", err);
    }
