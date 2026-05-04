from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from web_control.controller import RobotWebController


controller = RobotWebController()
app = FastAPI(title="Codenect4 Web Control")
WEB_CONTROL_VERSION = "minimal-dashboard-2026-05-04b"


class StartGameRequest(BaseModel):
    camera: int | None = None
    device: str | None = None
    width: int = 640
    height: int = 480
    depth: int = 5
    state_streak: int = 3


class ConfirmYellowRequest(BaseModel):
    accept: bool = True
    column: int | None = None


class SorterCalibrationLabelRequest(BaseModel):
    label: str


class ManualHumanMoveRequest(BaseModel):
    column: int


class RemovePieceRequest(BaseModel):
    row: int
    column: int


class BeltStartRequest(BaseModel):
    speed: int = 600
    accel: int = 400
    steps: int | None = None


class BeltSettingsRequest(BaseModel):
    speed: int = 600
    accel: int = 400
    steps: int | None = None
    launch_speed: int | None = None
    launch_accel: int | None = None
    launch_steps: int | None = None
    clear_thresh: float | None = None
    post_detect_delay_ms: int | None = None
    detect_integration_ms: int | None = None
    detect_samples: int | None = None
    detect_streak: int | None = None
    game_belt_enabled: bool | None = None


class BeltCalibrationActionRequest(BaseModel):
    action: str


class BeltReadyConfirmRequest(BaseModel):
    accept: bool = True


class GateStartRequest(BaseModel):
    speed: int = 600
    accel: int = 400
    steps: int | None = None


@app.get("/api/state")
def api_state():
    return controller.get_state()


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "codenect4-web",
        "version": WEB_CONTROL_VERSION,
    }


@app.post("/api/game/start")
def api_start_game(request: StartGameRequest):
    return controller.start_game(
        camera=request.camera,
        device=request.device,
        width=request.width,
        height=request.height,
        depth=request.depth,
        state_streak=request.state_streak,
    )


@app.post("/api/game/stop")
def api_stop_game():
    return controller.stop_game()


@app.post("/api/game/pause-toggle")
def api_pause_toggle_game():
    return controller.toggle_pause_game()


@app.post("/api/game/reset")
def api_reset_game(request: StartGameRequest):
    return controller.reset_game(
        camera=request.camera,
        device=request.device,
        width=request.width,
        height=request.height,
        depth=request.depth,
        state_streak=request.state_streak,
    )


@app.post("/api/game/yellow-confirm")
def api_confirm_yellow(request: ConfirmYellowRequest):
    return controller.confirm_yellow(accept=request.accept, column=request.column)


@app.post("/api/game/red-confirm")
def api_confirm_red():
    return controller.confirm_red()


@app.post("/api/game/manual-human-move")
def api_manual_human_move(request: ManualHumanMoveRequest):
    return controller.manual_human_move(request.column)


@app.post("/api/game/remove-piece")
def api_remove_piece(request: RemovePieceRequest):
    return controller.remove_piece(request.row, request.column)


@app.post("/api/sorting/enable")
def api_enable_sorting():
    return controller.enable_sorting()


@app.post("/api/sorting/disable")
def api_disable_sorting():
    return controller.disable_sorting()


@app.post("/api/sorting/calibration/start")
def api_start_sorter_calibration():
    return controller.start_sorter_calibration(sensor_bus=3)


@app.post("/api/sorting/calibration/label")
def api_sorter_calibration_label(request: SorterCalibrationLabelRequest):
    return controller.submit_sorter_calibration_label(request.label)


@app.post("/api/servos/zero")
def api_zero_servos():
    return controller.zero_servos()


@app.post("/api/belt/start")
def api_start_belt(request: BeltStartRequest):
    return controller.start_belt(speed=request.speed, accel=request.accel, steps=request.steps)


@app.post("/api/belt/stop")
def api_stop_belt():
    return controller.stop_belt()


@app.post("/api/belt/settings")
def api_belt_settings(request: BeltSettingsRequest):
    return controller.update_belt_settings(
        speed=request.speed,
        accel=request.accel,
        steps=request.steps,
        launch_speed=request.launch_speed,
        launch_accel=request.launch_accel,
        launch_steps=request.launch_steps,
        clear_thresh=request.clear_thresh,
        post_detect_delay_ms=request.post_detect_delay_ms,
        detect_integration_ms=request.detect_integration_ms,
        detect_samples=request.detect_samples,
        detect_streak=request.detect_streak,
        game_belt_enabled=request.game_belt_enabled,
    )


@app.post("/api/belt/calibration/start")
def api_start_belt_calibration():
    return controller.start_belt_calibration()


@app.post("/api/belt/calibration/action")
def api_belt_calibration_action(request: BeltCalibrationActionRequest):
    return controller.submit_belt_calibration_action(request.action)


@app.post("/api/belt/test/start")
def api_start_belt_test():
    return controller.start_belt_test()


@app.post("/api/belt/test/continue")
def api_continue_belt_test():
    return controller.continue_belt_test()


@app.post("/api/belt/test/stop")
def api_stop_belt_test():
    return controller.stop_belt_test()


@app.post("/api/belt/ready-confirm")
def api_belt_ready_confirm(request: BeltReadyConfirmRequest):
    return controller.set_belt_ready_confirmation(accept=request.accept)


@app.post("/api/gate/start")
def api_start_gate(request: GateStartRequest):
    return controller.start_gate(speed=request.speed, accel=request.accel, steps=request.steps)


@app.post("/api/gate/stop")
def api_stop_gate():
    return controller.stop_gate()


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(PAGE_HTML)


def main():
    import uvicorn

    uvicorn.run("web_control.server:app", host="0.0.0.0", port=8000, reload=False)


PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Connect4 Dashboard</title>
  <style>
    :root {
      --bg: #eef1f4;
      --bg-top: #f7f8fa;
      --panel: rgba(255, 255, 255, 0.92);
      --panel-soft: #f3f5f7;
      --line: rgba(16, 24, 40, 0.08);
      --line-strong: rgba(16, 24, 40, 0.16);
      --ink: #111827;
      --muted: #6b7280;
      --accent: #3768d7;
      --accent-soft: rgba(55, 104, 215, 0.08);
      --ok: #1f8f72;
      --ok-soft: rgba(31, 143, 114, 0.1);
      --warn: #d6941f;
      --warn-soft: rgba(214, 148, 31, 0.1);
      --danger: #d0493e;
      --danger-soft: rgba(208, 73, 62, 0.1);
      --red: #ff5e52;
      --yellow: #ffd15a;
      --board-top: #2f74ff;
      --board-bottom: #123983;
      --slot-empty: #dbe7ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: Inter, "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(55,104,215,0.06) 0%, transparent 24%),
        linear-gradient(180deg, var(--bg-top) 0%, var(--bg) 100%);
    }
    .wrap {
      max-width: 1120px;
      margin: 0 auto;
      padding: 18px 16px 28px;
    }
    .masthead {
      display: grid;
      gap: 4px;
      margin-bottom: 12px;
    }
    h1 {
      margin: 0;
      font-size: 2rem;
      line-height: 1;
      letter-spacing: -0.06em;
      font-weight: 780;
    }
    .layout {
      display: grid;
      gap: 14px;
      align-items: start;
    }
    @media (min-width: 980px) {
      .layout {
        grid-template-columns: minmax(0, 1.12fr) minmax(300px, 0.78fr);
      }
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      backdrop-filter: blur(10px);
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
    }
    .banner {
      padding: 12px 14px 14px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.72) 0%, rgba(255,255,255,0.3) 100%);
    }
    .banner-label {
      margin-bottom: 8px;
      color: #637083;
      font-size: 0.7rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.18em;
    }
    .banner-title {
      font-size: 1.36rem;
      line-height: 0.98;
      letter-spacing: -0.05em;
      font-weight: 800;
    }
    .banner-copy {
      margin-top: 8px;
      color: var(--muted);
      line-height: 1.42;
      font-size: 0.9rem;
      max-width: 50rem;
    }
    .banner.thinking {
      background: #eef4ff;
    }
    .banner.waiting {
      background: linear-gradient(180deg, var(--warn-soft) 0%, rgba(255,191,71,0.02) 100%);
    }
    .banner.ready {
      background: linear-gradient(180deg, var(--ok-soft) 0%, rgba(63,214,180,0.02) 100%);
    }
    .board-wrap {
      padding: 10px 14px 14px;
    }
    .cols {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 6px;
      margin-bottom: 6px;
      max-width: 380px;
      width: 100%;
      margin-left: auto;
      margin-right: auto;
      text-align: center;
      color: #7b8491;
      font-size: 0.68rem;
      font-weight: 800;
      letter-spacing: 0.12em;
    }
    .board {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 6px;
      padding: 10px;
      max-width: 380px;
      width: 100%;
      margin: 0 auto;
      border-radius: 9px;
      background: #2156c7;
      box-shadow: 0 7px 14px rgba(15, 23, 42, 0.09);
    }
    .slot {
      aspect-ratio: 1;
      border-radius: 999px;
      background: #d7e1f5;
      border: 2px solid rgba(255,255,255,0.10);
      box-shadow: inset 0 2px 6px rgba(10,20,40,0.16);
    }
    .slot.red {
      background: #bf3f35;
    }
    .slot.yellow {
      background: #d7a51d;
    }
    .slot.pending-yellow {
      background: #f1d770;
      opacity: 0.84;
      box-shadow: inset 0 4px 10px rgba(120,90,0,0.12), 0 0 0 3px rgba(255,209,90,0.28);
    }
    .slot.manual-yellow {
      box-shadow: inset 0 2px 6px rgba(10,20,40,0.16), 0 0 0 3px rgba(55,104,215,0.18);
    }
    .slot.clickable {
      cursor: pointer;
      transition: transform 120ms ease, opacity 120ms ease;
    }
    .slot.clickable:hover {
      transform: scale(1.02);
    }
    .legend {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.74rem;
      justify-content: center;
    }
    .legend-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .legend-dot {
      width: 12px;
      height: 12px;
      border-radius: 999px;
    }
    .legend-dot.red { background: var(--red); }
    .legend-dot.yellow { background: var(--yellow); }
    .legend-dot.empty { background: var(--slot-empty); border: 1px solid #a9bcdf; }
    .section {
      padding: 12px 14px 14px;
    }
    .section-title {
      margin: 0 0 12px;
      color: #637083;
      font-size: 0.74rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.18em;
    }
    .state-grid {
      display: grid;
      gap: 10px;
    }
    @media (min-width: 980px) {
      .state-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    .state-box {
      padding: 10px 11px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
    }
    .state-box h3 {
      margin: 0 0 6px;
      color: #7b8491;
      font-size: 0.7rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 800;
    }
    .state-kv {
      display: grid;
      gap: 4px;
    }
    .state-row {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 0.84rem;
      line-height: 1.25;
    }
    .state-row span:first-child {
      color: var(--muted);
    }
    .state-row strong {
      text-align: right;
    }
    .controls {
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(auto-fit, minmax(138px, 1fr));
    }
    .controls.spaced-top {
      margin-top: 8px;
    }
    .controls.one-line {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .field-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-bottom: 12px;
    }
    .field {
      display: grid;
      gap: 6px;
    }
    .field label {
      color: var(--muted);
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .field input {
      width: 100%;
      padding: 10px 11px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: white;
      color: var(--ink);
      font: inherit;
    }
    button {
      appearance: none;
      border: 1px solid transparent;
      border-radius: 8px;
      padding: 11px 13px;
      font: inherit;
      font-weight: 700;
      color: white;
      background: var(--accent);
      cursor: pointer;
      transition: opacity 120ms ease, transform 120ms ease;
    }
    button:hover {
      opacity: 0.96;
      transform: translateY(-1px);
    }
    button:disabled {
      opacity: 0.45;
      transform: none;
      cursor: not-allowed;
    }
    button.warning { background: var(--warn); color: #281800; }
    button.danger { background: var(--danger); }
    button.ok { background: var(--ok); }
    button.secondary { background: #6b7280; }
    .confirm-panel {
      padding: 16px 18px 18px;
      border-top: 1px solid var(--line);
    }
    .confirm-panel.hidden {
      display: none;
    }
    .confirm-title {
      margin: 0 0 8px;
      font-size: 1rem;
      letter-spacing: -0.02em;
      font-weight: 760;
    }
    .confirm-copy {
      margin: 0 0 12px;
      color: var(--muted);
      line-height: 1.45;
      font-size: 0.92rem;
    }
    .thinking-line {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
    }
    .loading-dots {
      display: inline-flex;
      gap: 4px;
      transform: translateY(1px);
    }
    .loading-dots span {
      width: 6px;
      height: 6px;
      border-radius: 999px;
      background: rgba(17, 24, 39, 0.48);
      animation: pulseDot 1s infinite ease-in-out;
    }
    .loading-dots span:nth-child(2) { animation-delay: 0.16s; }
    .loading-dots span:nth-child(3) { animation-delay: 0.32s; }
    @keyframes pulseDot {
      0%, 80%, 100% { opacity: 0.28; transform: scale(0.8); }
      40% { opacity: 1; transform: scale(1); }
    }
    .footer-note {
      margin-top: 14px;
      text-align: center;
      color: var(--muted);
      font-size: 0.8rem;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="masthead">
      <h1>Connect4 Dashboard</h1>
    </div>

    <div class="layout">
      <div class="stack">
        <div class="panel">
          <div id="turnBanner" class="banner">
            <div class="banner-label">Primary State</div>
            <div id="bannerTitle" class="banner-title">Idle</div>
            <div id="bannerText" class="banner-copy">Start the game loop when you're ready.</div>
          </div>
          <div class="board-wrap">
            <div class="cols"><div>6</div><div>5</div><div>4</div><div>3</div><div>2</div><div>1</div><div>0</div></div>
            <div id="board" class="board"></div>
            <div class="legend">
              <div class="legend-chip"><span class="legend-dot yellow"></span><span>Player / Yellow</span></div>
              <div class="legend-chip"><span class="legend-dot red"></span><span>Computer / Red</span></div>
              <div class="legend-chip"><span class="legend-dot empty"></span><span>Empty</span></div>
            </div>
          </div>
        </div>

        <div class="panel section">
          <div class="section-title">Game Controls</div>
          <div class="controls">
            <button id="primaryGameButton" onclick="handlePrimaryGameAction()">Start Game</button>
            <button class="warning" onclick="resetGame()">Reset Game</button>
          </div>
          <div id="beltReadyControls" class="controls hidden spaced-top">
            <button id="beltReadyConfirmButton" class="ok" onclick="confirmBeltReady(true)">Confirm Ready</button>
            <button id="beltReadyRejectButton" class="secondary" onclick="confirmBeltReady(false)">False Positive</button>
          </div>
        </div>
      </div>

      <div class="stack">
        <div class="panel section">
          <div class="section-title">System State</div>
          <div class="state-grid">
            <div class="state-box">
              <h3>Game State</h3>
              <div class="state-kv">
                <div class="state-row"><span>Status</span><strong id="metaStatus">idle</strong></div>
                <div class="state-row"><span>Phase</span><strong id="stateGamePhase">idle</strong></div>
                <div class="state-row"><span>Turn</span><strong id="stateTurnState">idle</strong></div>
                <div class="state-row"><span>Winner</span><strong id="stateWinner">none</strong></div>
                <div class="state-row"><span>Running</span><strong id="stateGameRunning">no</strong></div>
              </div>
            </div>
            <div class="state-box">
              <h3>Vision</h3>
              <div class="state-kv">
                <div class="state-row"><span>Tracker</span><strong id="metaTracker">calibrating</strong></div>
                <div class="state-row"><span>Tracker active</span><strong id="stateTrackerActive">no</strong></div>
                <div class="state-row"><span>Camera</span><strong id="metaCamera">n/a</strong></div>
                <div class="state-row"><span>Awaiting</span><strong id="stateAwaiting">none</strong></div>
                <div class="state-row"><span>Updated</span><strong id="stateUpdated">-</strong></div>
              </div>
            </div>
            <div class="state-box">
              <h3>Pieces</h3>
              <div class="state-kv">
                <div class="state-row"><span>Yellow confirmed</span><strong id="stateYellowCount">0</strong></div>
                <div class="state-row"><span>Red confirmed</span><strong id="stateRedCount">0</strong></div>
                <div class="state-row"><span>Pending yellow</span><strong id="statePendingYellow">0</strong></div>
                <div class="state-row"><span>Yellow column</span><strong id="stateYellowCol">-</strong></div>
                <div class="state-row"><span>Red column</span><strong id="stateRedCol">-</strong></div>
              </div>
            </div>
            <div class="state-box">
              <h3>Subsystems</h3>
              <div class="state-kv">
                <div class="state-row"><span>Sorting enabled</span><strong id="stateSortingEnabled">no</strong></div>
                <div class="state-row"><span>Sorter process</span><strong id="stateSorterRunning">off</strong></div>
                <div class="state-row"><span>Calibration</span><strong id="stateSorterCalibration">idle</strong></div>
                <div class="state-row"><span>Suggested red</span><strong id="metaRed">-</strong></div>
                <div class="state-row"><span>Tracker calibrated</span><strong id="stateTrackerCalibrated">no</strong></div>
                <div class="state-row"><span>Camera source</span><strong id="stateCameraSource">n/a</strong></div>
              </div>
            </div>
          </div>
        </div>

        <div id="yellowCard" class="panel confirm-panel hidden">
          <div class="section-title">Yellow Confirmation</div>
          <div class="confirm-title">Validate player move</div>
          <div id="yellowCopy" class="confirm-copy">Tap the highlighted yellow slot to confirm it, or tap another slot in the correct column to override it.</div>
        </div>

        <div id="redCard" class="panel confirm-panel hidden">
          <div class="section-title">Red Placement</div>
          <div class="confirm-title">Confirm robot output</div>
          <div id="redCopy" class="confirm-copy">The computer has chosen a red column. Place the piece and let vision confirm it automatically.</div>
          <div class="controls">
            <button class="warning" onclick="confirmRed()">Red Piece Placed</button>
          </div>
        </div>

        <div class="panel section">
          <div class="section-title">Sorting Controls</div>
          <div class="controls one-line">
            <button class="ok" onclick="enableSorting()">Enable Sorting</button>
            <button class="secondary" onclick="disableSorting()">Disable Sorting</button>
            <button onclick="startSorterCalibration()">Start Sorter Calibration</button>
          </div>
        </div>

        <div id="sorterCalibrationCard" class="panel confirm-panel hidden">
          <div class="section-title">Sorter Calibration</div>
          <div id="sorterCalibrationTitle" class="confirm-title">Calibration active</div>
          <div id="sorterCalibrationCopy" class="confirm-copy">Calibration will step the sorter to detect and wait for a label. Future sorting runs will use the saved values.</div>
          <div id="sorterCalibrationSample" class="confirm-copy">No sample yet.</div>
          <div id="sorterCalibrationCounts" class="confirm-copy">red 0 | yellow 0 | none 0</div>
          <div class="controls">
            <button id="sorterLabelRed" class="danger" onclick="labelSorterCalibration('r')">Red</button>
            <button id="sorterLabelYellow" class="warning" onclick="labelSorterCalibration('y')">Yellow</button>
            <button id="sorterLabelNone" class="secondary" onclick="labelSorterCalibration('n')">None</button>
            <button id="sorterLabelAgitate" class="secondary" onclick="labelSorterCalibration('a')">Agitate</button>
            <button id="sorterLabelQuit" class="ok" onclick="labelSorterCalibration('q')">Quit</button>
          </div>
        </div>

        <div class="panel section">
          <div class="section-title">Servo Controls</div>
          <div class="controls">
            <button class="secondary" onclick="zeroServos()">Zero All Servos</button>
          </div>
        </div>

        <div class="panel section">
          <div class="section-title">Belt Control</div>
          <div class="field-grid">
            <div class="field">
              <label for="beltSpeed">Speed</label>
              <input id="beltSpeed" type="number" inputmode="numeric" value="600">
            </div>
            <div class="field">
              <label for="beltAccel">Accel</label>
              <input id="beltAccel" type="number" inputmode="numeric" value="400">
            </div>
            <div class="field">
              <label for="beltSteps">Steps</label>
              <input id="beltSteps" type="number" inputmode="numeric">
            </div>
          </div>
          <div class="field-grid">
            <div class="field">
              <label for="beltClearThresh">Clear Threshold</label>
              <input id="beltClearThresh" type="number" inputmode="decimal" value="2500">
            </div>
            <div class="field">
              <label for="beltPostDetectDelayMs">Post-Detect Delay (ms)</label>
              <input id="beltPostDetectDelayMs" type="number" inputmode="numeric" value="500">
            </div>
            <div class="field">
              <label>Game Loop Mode</label>
              <button id="gameBeltModeButton" class="secondary" onclick="toggleGameBeltMode()">Game Belt: On</button>
            </div>
          </div>
          <div class="field-grid">
            <div class="field">
              <label for="beltDetectIntegrationMs">Detect Integration (ms)</label>
              <input id="beltDetectIntegrationMs" type="number" inputmode="numeric" value="24">
            </div>
            <div class="field">
              <label for="beltDetectSamples">Detect Samples</label>
              <input id="beltDetectSamples" type="number" inputmode="numeric" value="1">
            </div>
            <div class="field">
              <label for="beltDetectStreak">Detect Streak</label>
              <input id="beltDetectStreak" type="number" inputmode="numeric" value="1">
            </div>
          </div>
          <div class="field-grid">
            <div class="field">
              <label for="beltLaunchSpeed">Launch Speed</label>
              <input id="beltLaunchSpeed" type="number" inputmode="numeric" value="4000">
            </div>
            <div class="field">
              <label for="beltLaunchAccel">Launch Accel</label>
              <input id="beltLaunchAccel" type="number" inputmode="numeric" value="400">
            </div>
            <div class="field">
              <label for="beltLaunchSteps">Launch Steps</label>
              <input id="beltLaunchSteps" type="number" inputmode="numeric" value="1500">
            </div>
          </div>
          <div class="controls">
            <button class="secondary" onclick="startBeltCalibration()">Calibrate Belt TCS</button>
          </div>
          <div class="controls spaced-top">
            <button id="beltTestButton" class="secondary" onclick="toggleBeltTest()">Test Belt Calibration</button>
            <button id="beltTestContinueButton" class="warning" onclick="continueBeltTest()">Continue</button>
          </div>
          <div class="confirm-copy" id="beltStatusText">Belt idle.</div>
          <div class="controls">
            <button id="beltActionButton" class="ok" onclick="toggleBelt()">Start Belt</button>
          </div>
        </div>

        <div id="beltCalibrationCard" class="panel confirm-panel hidden">
          <div class="section-title">Belt Calibration</div>
          <div class="confirm-title">Clear threshold calibration</div>
          <div id="beltCalibrationCopy" class="confirm-copy">Capture empty and covered-piece samples to suggest a clear threshold.</div>
          <div id="beltCalibrationSample" class="confirm-copy">No sample yet.</div>
          <div id="beltCalibrationCounts" class="confirm-copy">empty 0 | piece 0</div>
          <div class="controls">
            <button id="beltCaptureEmpty" class="secondary" onclick="beltCalibrationAction('empty')">Capture Empty</button>
            <button id="beltCapturePiece" class="warning" onclick="beltCalibrationAction('piece')">Capture Piece</button>
            <button id="beltFinishCalibration" class="ok" onclick="beltCalibrationAction('finish')">Finish</button>
            <button id="beltCancelCalibration" class="danger" onclick="beltCalibrationAction('cancel')">Cancel</button>
          </div>
        </div>

        <div class="panel section">
          <div class="section-title">Gate Stepper</div>
          <div class="field-grid">
            <div class="field">
              <label for="gateSpeed">Speed</label>
              <input id="gateSpeed" type="number" inputmode="numeric" value="600">
            </div>
            <div class="field">
              <label for="gateAccel">Accel</label>
              <input id="gateAccel" type="number" inputmode="numeric" value="400">
            </div>
            <div class="field">
              <label for="gateSteps">Steps</label>
              <input id="gateSteps" type="number" inputmode="numeric" value="1000">
            </div>
          </div>
          <div class="confirm-copy" id="gateStatusText">Gate stepper idle.</div>
          <div class="controls">
            <button id="gateActionButton" class="ok" onclick="toggleGate()">Start Gate</button>
          </div>
        </div>
      </div>
    </div>

    <div class="footer-note">
      <span id="versionBadge">version: loading</span>
    </div>
  </div>

  <script>
    let latestState = null;
    let healthState = null;

    async function api(path, method = "GET", body = null) {
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : null
      });
      return res.json();
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

    function renderBoard(board) {
      const root = document.getElementById("board");
      root.innerHTML = "";
      if (!board) return;
      const mirrored = board.map(row => [...row].reverse());
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
          text: state.message || "Keep the board visible and empty for a moment.",
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

    async function refresh() {
      latestState = await api("/api/state");
      renderBanner(latestState);
      renderMeta(latestState);
      renderStateBlocks(latestState);
      renderGameControls(latestState);
      renderBeltPanel(latestState);
      renderBeltCalibration(latestState);
      renderGatePanel(latestState);
      renderSorterCalibration(latestState);
      renderConfirmationCards(latestState);
      renderBoard(latestState.current_board);
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

    ["beltSpeed", "beltAccel", "beltSteps", "beltClearThresh", "beltPostDetectDelayMs", "beltDetectIntegrationMs", "beltDetectSamples", "beltDetectStreak", "beltLaunchSpeed", "beltLaunchAccel", "beltLaunchSteps"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("change", () => {
          syncBeltSettings().catch(() => {});
        });
      }
    });

    refreshHealth();
    refresh();
    setInterval(refreshHealth, 5000);
    setInterval(refresh, 800);
  </script>
</body>
</html>
"""
