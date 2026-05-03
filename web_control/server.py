from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from web_control.controller import RobotWebController


controller = RobotWebController()
app = FastAPI(title="Codenect4 Web Control")
WEB_CONTROL_VERSION = "minimal-dashboard-2026-05-03g"


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


class BeltStartRequest(BaseModel):
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
    .state-box {
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
    }
    .state-box h3 {
      margin: 0 0 8px;
      color: #7b8491;
      font-size: 0.7rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 800;
    }
    .state-kv {
      display: grid;
      gap: 6px;
    }
    .state-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: 0.88rem;
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
            <button onclick="startGame()">Start Game</button>
            <button class="warning" onclick="resetGame()">Reset Game</button>
            <button class="danger" onclick="stopGame()">Stop Game</button>
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
          <div id="redCopy" class="confirm-copy">The computer has chosen a red column. Place the piece, then confirm it here.</div>
          <div class="controls">
            <button class="warning" onclick="confirmRed()">Red Piece Placed</button>
          </div>
        </div>

        <div class="panel section">
          <div class="section-title">Sorting Controls</div>
          <div class="controls">
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
          <div class="confirm-copy" id="beltStatusText">Belt idle.</div>
          <div class="controls">
            <button id="beltActionButton" class="ok" onclick="toggleBelt()">Start Belt</button>
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
      await api("/api/game/start", "POST", { device: "/dev/video0", width: 640, height: 480, depth: 5, state_streak: 3 });
      await refresh();
    }

    async function stopGame() {
      await api("/api/game/stop", "POST");
      await refresh();
    }

    async function resetGame() {
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

    async function toggleBelt() {
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

    async function handleBoardClick(visibleColumn, isPendingCell) {
      if (!latestState) return;
      if (
        latestState.game_status === "waiting_human_move" ||
        latestState.turn_state === "human_turn"
      ) {
        await manualYellowMove(visibleColumn);
        return;
      }
      if (latestState.awaiting_confirmation === "yellow") {
        if (isPendingCell) {
          await confirmYellow(true);
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
            slot.title = `Register yellow in column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, false));
          } else if (latestState && latestState.awaiting_confirmation === "yellow") {
            slot.classList.add("clickable");
            slot.title = isPending
              ? `Confirm detected yellow in column ${originalCol}`
              : `Override to column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, isPending));
          } else if (
            latestState &&
            latestState.awaiting_confirmation === "red" &&
            latestState.suggested_red_column !== null &&
            originalCol === latestState.suggested_red_column
          ) {
            slot.classList.add("clickable");
            slot.title = `Confirm red placement in column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, false));
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
          text: state.prompt || "Drop the red piece on the real board and confirm it here.",
        };
      }
      if (state.game_status === "thinking") {
        return {
          className: "banner thinking",
          title: "Computer is thinking",
          text: "",
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
      if (!status || !button) return;

      if (state.belt_running) {
        const modeText = state.belt_mode === "steps"
          ? `Running ${state.belt_steps ?? "-"} steps at ${state.belt_speed} / accel ${state.belt_accel}.`
          : `Running continuously at ${state.belt_speed} / accel ${state.belt_accel}.`;
        status.textContent = modeText;
        button.textContent = "Stop Belt";
        button.className = "danger";
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

    function renderSorterCalibration(state) {
      const card = document.getElementById("sorterCalibrationCard");
      const title = document.getElementById("sorterCalibrationTitle");
      const copy = document.getElementById("sorterCalibrationCopy");
      const sample = document.getElementById("sorterCalibrationSample");
      const counts = document.getElementById("sorterCalibrationCounts");
      const redBtn = document.getElementById("sorterLabelRed");
      const yellowBtn = document.getElementById("sorterLabelYellow");
      const noneBtn = document.getElementById("sorterLabelNone");
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
        redCopy.textContent = state.prompt || "Place the red piece and confirm it here.";
      }
      if (state.awaiting_confirmation !== "yellow" && state.awaiting_confirmation !== "red") {
        yellowCopy.textContent = "Detected a yellow move. Confirm it or correct the column.";
        redCopy.textContent = "The computer has chosen a red column. Place the piece, then confirm it here.";
      }
    }

    async function refresh() {
      latestState = await api("/api/state");
      renderBanner(latestState);
      renderMeta(latestState);
      renderStateBlocks(latestState);
      renderBeltPanel(latestState);
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

    refreshHealth();
    refresh();
    setInterval(refreshHealth, 5000);
    setInterval(refresh, 800);
  </script>
</body>
</html>
"""
