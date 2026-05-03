from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from web_control.controller import RobotWebController


controller = RobotWebController()
app = FastAPI(title="Codenect4 Web Control")
WEB_CONTROL_VERSION = "web-ui-2026-05-03a"


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


class ManualMoveRequest(BaseModel):
    column: int


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


@app.post("/api/game/manual-human")
def api_manual_human(request: ManualMoveRequest):
    return controller.manual_human_move(request.column)


@app.post("/api/sorting/enable")
def api_enable_sorting():
    return controller.enable_sorting()


@app.post("/api/sorting/disable")
def api_disable_sorting():
    return controller.disable_sorting()


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
  <title>Codenect4 Control</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --card: rgba(255, 255, 255, 0.94);
      --card-strong: #ffffff;
      --ink: #101828;
      --muted: #667085;
      --accent: #2563eb;
      --accent-deep: #173b87;
      --warn: #b96a15;
      --danger: #c53f35;
      --ok: #147d6f;
      --line: #e7eaf0;
      --line-strong: #d0d5dd;
      --red: #df473c;
      --yellow: #f3c94f;
      --board-blue-top: #2f63da;
      --board-blue-bottom: #173a88;
      --slot-empty: #eff3ff;
    }
    body {
      margin: 0;
      font-family: Inter, "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(37,99,235,0.06) 0%, transparent 28%),
        linear-gradient(180deg, #f8fbff 0%, var(--bg) 44%, #f6f8fc 100%);
      color: var(--ink);
    }
    .wrap {
      max-width: 960px;
      margin: 0 auto;
      padding: 16px 16px 48px;
    }
    .hero {
      background: transparent;
      border: 0;
      border-radius: 0;
      padding: 4px 0 8px;
      backdrop-filter: none;
      box-shadow: none;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 1.95rem;
      letter-spacing: 0.02em;
      font-weight: 760;
    }
    .sub {
      margin: 0;
      color: var(--muted);
      max-width: 36rem;
      font-size: 0.98rem;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 6px 18px rgba(16, 24, 40, 0.04);
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    .hero-grid {
      display: grid;
      gap: 12px;
      margin-top: 14px;
    }
    @media (min-width: 820px) {
      .hero-grid {
        grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
        align-items: start;
      }
      .hero-grid > .stack:first-child { order: 2; }
      .hero-grid > .stack:last-child { order: 1; }
    }
    .controls {
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    }
    button {
      border: 1px solid transparent;
      border-radius: 10px;
      padding: 11px 13px;
      font: inherit;
      font-weight: 650;
      background: var(--accent);
      color: white;
      cursor: pointer;
      box-shadow: none;
      transition: background 120ms ease, transform 120ms ease, opacity 120ms ease, border-color 120ms ease;
    }
    button:hover {
      opacity: 0.96;
    }
    button.secondary { background: #475467; }
    button.warning { background: var(--warn); }
    button.danger { background: var(--danger); }
    button.ok { background: var(--ok); }
    button.ghost {
      background: #ffffff;
      color: var(--ink);
      border: 1px solid var(--line-strong);
      box-shadow: none;
    }
    h2 {
      margin: 0 0 12px;
      font-size: 0.96rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .status-pill {
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      background: #f2f4f7;
      color: #344054;
      font-size: 0.75rem;
      font-weight: 700;
      margin-right: 6px;
      margin-bottom: 6px;
      border: 1px solid #eaecf0;
    }
    .banner {
      border-radius: 12px;
      padding: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.94);
    }
    .banner.kicker {
      display: inline-block;
      font-size: 0.82rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 700;
      margin-bottom: 8px;
    }
    .banner h2 {
      margin: 0;
      font-size: 1.25rem;
    }
    .banner p {
      margin: 8px 0 0;
      color: var(--muted);
    }
    .banner.thinking {
      background: #eef4ff;
      border-color: #cadeff;
    }
    .banner.waiting {
      background: #fff6e8;
      border-color: #f2d39c;
    }
    .banner.ready {
      background: #ebfaf7;
      border-color: #b6e2d8;
    }
    .confirm-card {
      border-radius: 12px;
      padding: 16px;
      border: 1px solid var(--line-strong);
      background: #ffffff;
    }
    .confirm-card.hidden {
      display: none;
    }
    .confirm-title {
      margin: 0 0 8px;
      font-size: 1.05rem;
    }
    .confirm-copy {
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.4;
    }
    .board {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 10px;
      margin-top: 14px;
      background:
        radial-gradient(circle at top, rgba(255,255,255,0.18) 0%, transparent 30%),
        linear-gradient(180deg, var(--board-blue-top) 0%, var(--board-blue-bottom) 100%);
      padding: 18px;
      border-radius: 16px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.12), 0 12px 22px rgba(22,57,131,0.16);
    }
    .slot {
      aspect-ratio: 1;
      border-radius: 999px;
      background:
        radial-gradient(circle at 35% 30%, #ffffff 0%, #f2f6ff 25%, var(--slot-empty) 60%, #d9e2f5 100%);
      border: 2px solid rgba(255,255,255,0.18);
      box-shadow:
        inset 0 6px 12px rgba(0,0,0,0.18),
        0 2px 0 rgba(255,255,255,0.12);
    }
    .slot.red {
      background: radial-gradient(circle at 35% 30%, #ff9486 0%, #f54f3d 28%, var(--red) 68%, #8f1911 100%);
    }
    .slot.yellow {
      background: radial-gradient(circle at 35% 30%, #fff4a8 0%, #fbe171 32%, var(--yellow) 70%, #c79212 100%);
    }
    .slot.pending-yellow {
      background: radial-gradient(circle at 35% 30%, #fffad1 0%, #fff2a0 34%, #f7da6d 68%, #e0bf49 100%);
      opacity: 0.78;
      border-color: rgba(255,255,255,0.42);
      box-shadow:
        inset 0 4px 10px rgba(120,90,0,0.15),
        0 0 0 3px rgba(243, 201, 79, 0.32);
    }
    .slot.clickable {
      cursor: pointer;
    }
    .slot.clickable:hover {
      transform: scale(1.03);
    }
    .cols {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 8px;
      margin-top: 6px;
      text-align: center;
      font-weight: 700;
      color: #35518a;
      letter-spacing: 0.04em;
    }
    .legend {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 12px;
      color: var(--muted);
      font-size: 0.86rem;
    }
    .legend-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .legend-disc {
      width: 14px;
      height: 14px;
      border-radius: 999px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.4);
    }
    .legend-disc.red { background: var(--red); }
    .legend-disc.yellow { background: var(--yellow); }
    .legend-disc.empty { background: var(--slot-empty); border: 1px solid #cad7ec; }
    .meta {
      display: grid;
      gap: 4px;
    }
    .meta-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid #edf0f5;
    }
    .meta-row:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }
    .meta-label {
      color: var(--muted);
      font-size: 0.9rem;
    }
    .meta-value {
      font-weight: 700;
      text-align: right;
    }
    .state-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 14px;
    }
    .state-block {
      border: 1px solid var(--line);
      background: #fafbfc;
      padding: 12px;
      border-radius: 10px;
    }
    .state-block h3 {
      margin: 0 0 8px;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    .state-kv {
      display: grid;
      gap: 6px;
    }
    .state-kv-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 0.9rem;
    }
    .state-kv-row span:first-child {
      color: var(--muted);
    }
    .mono {
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 0.84rem;
    }
    .thinking::after {
      content: "";
      animation: dots 1.2s steps(4, end) infinite;
    }
    @keyframes dots {
      0% { content: ""; }
      25% { content: "."; }
      50% { content: ".."; }
      75% { content: "..."; }
      100% { content: ""; }
    }
    input[type=number] {
      width: 100%;
      box-sizing: border-box;
      border-radius: 12px;
      border: 1px solid var(--line-strong);
      padding: 10px 12px;
      font: inherit;
      margin-top: 8px;
      background: rgba(255,255,255,0.84);
    }
    .muted {
      color: var(--muted);
    }
    .footer-note {
      margin-top: 14px;
      text-align: center;
      color: var(--muted);
      font-size: 0.85rem;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Connect4 Control</h1>
    </div>

    <div class="hero-grid">
      <div class="stack">
        <div class="card">
          <div id="turnBanner" class="banner">
            <div class="kicker">Game Flow</div>
            <h2 id="bannerTitle">Idle</h2>
            <p id="bannerText">Start the game loop when you're ready.</p>
          </div>
          <div class="cols"><div>6</div><div>5</div><div>4</div><div>3</div><div>2</div><div>1</div><div>0</div></div>
          <div id="board" class="board"></div>
          <div class="legend">
            <div class="legend-chip"><span class="legend-disc yellow"></span><span>You / Yellow</span></div>
            <div class="legend-chip"><span class="legend-disc red"></span><span>Computer / Red</span></div>
            <div class="legend-chip"><span class="legend-disc empty"></span><span>Empty</span></div>
          </div>
        </div>
      </div>

      <div class="stack">
        <div class="card">
          <h2>System</h2>
          <div id="pills"></div>
          <div class="meta">
            <div class="meta-row"><div class="meta-label">Status</div><div id="metaStatus" class="meta-value">idle</div></div>
            <div class="meta-row"><div class="meta-label">Tracker</div><div id="metaTracker" class="meta-value">calibrating</div></div>
            <div class="meta-row"><div class="meta-label">Camera</div><div id="metaCamera" class="meta-value">n/a</div></div>
            <div class="meta-row"><div class="meta-label">Suggested Red</div><div id="metaRed" class="meta-value">-</div></div>
          </div>
          <div class="state-grid">
            <div class="state-block">
              <h3>Game State</h3>
              <div class="state-kv">
                <div class="state-kv-row"><span>Running</span><strong id="stateGameRunning">no</strong></div>
                <div class="state-kv-row"><span>Phase</span><strong id="stateGamePhase">idle</strong></div>
                <div class="state-kv-row"><span>Turn</span><strong id="stateTurnState">idle</strong></div>
                <div class="state-kv-row"><span>Winner</span><strong id="stateWinner">none</strong></div>
              </div>
            </div>
            <div class="state-block">
              <h3>Subsystems</h3>
              <div class="state-kv">
                <div class="state-kv-row"><span>Sorting enabled</span><strong id="stateSortingEnabled">no</strong></div>
                <div class="state-kv-row"><span>Sorter process</span><strong id="stateSorterRunning">off</strong></div>
                <div class="state-kv-row"><span>Tracker active</span><strong id="stateTrackerActive">no</strong></div>
                <div class="state-kv-row"><span>Calibrated</span><strong id="stateTrackerCalibrated">no</strong></div>
              </div>
            </div>
            <div class="state-block">
              <h3>Pieces</h3>
              <div class="state-kv">
                <div class="state-kv-row"><span>Confirmed yellow</span><strong id="stateYellowCount">0</strong></div>
                <div class="state-kv-row"><span>Confirmed red</span><strong id="stateRedCount">0</strong></div>
                <div class="state-kv-row"><span>Pending yellow</span><strong id="statePendingYellow">0</strong></div>
                <div class="state-kv-row"><span>Awaiting</span><strong id="stateAwaiting">none</strong></div>
              </div>
            </div>
            <div class="state-block">
              <h3>Runtime</h3>
              <div class="state-kv">
                <div class="state-kv-row"><span>Camera source</span><strong id="stateCameraSource" class="mono">n/a</strong></div>
                <div class="state-kv-row"><span>Yellow column</span><strong id="stateYellowCol">-</strong></div>
                <div class="state-kv-row"><span>Red column</span><strong id="stateRedCol">-</strong></div>
                <div class="state-kv-row"><span>Updated</span><strong id="stateUpdated" class="mono">-</strong></div>
              </div>
            </div>
          </div>
        </div>

        <div id="yellowCard" class="confirm-card hidden">
          <h2 class="confirm-title">Yellow Confirmation</h2>
          <p id="yellowCopy" class="confirm-copy">Tap the highlighted yellow slot to confirm it, or tap a different slot in the correct column to override it.</p>
        </div>

        <div id="redCard" class="confirm-card hidden">
          <h2 class="confirm-title">Red Placement</h2>
          <p id="redCopy" class="confirm-copy">The computer has chosen a red column. Place the piece, then confirm it here.</p>
          <div class="controls">
            <button class="warning" onclick="confirmRed()">Red Piece Placed</button>
          </div>
        </div>

        <div class="card">
          <h2>Game Controls</h2>
          <div class="controls">
            <button onclick="startGame()">Start Game</button>
            <button class="warning" onclick="resetGame()">Reset Game</button>
            <button class="danger" onclick="stopGame()">Stop Game</button>
          </div>
        </div>

        <div class="card">
          <h2>Sorting Controls</h2>
          <div class="controls">
            <button class="ok" onclick="enableSorting()">Enable Sorting</button>
            <button class="secondary" onclick="disableSorting()">Disable Sorting</button>
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

    async function confirmYellow(accept) {
      await api("/api/game/yellow-confirm", "POST", { accept });
      await refresh();
    }

    async function confirmRed() {
      await api("/api/game/red-confirm", "POST");
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
      if (!latestState || latestState.awaiting_confirmation !== "yellow") return;
      if (isPendingCell) {
        await confirmYellow(true);
        return;
      }
      await api("/api/game/yellow-confirm", "POST", { accept: false, column: visibleColumn });
      await refresh();
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
          if (latestState && latestState.awaiting_confirmation === "yellow") {
            slot.classList.add("clickable");
            slot.title = isPending
              ? `Confirm detected yellow in column ${originalCol}`
              : `Override to column ${originalCol}`;
            slot.addEventListener("click", () => handleBoardClick(originalCol, isPending));
          }
          root.appendChild(slot);
        }
      }
    }

    function renderPills(state) {
      const pills = [];
      pills.push(`<span class="status-pill">status: ${state.game_status}</span>`);
      pills.push(`<span class="status-pill">sorting: ${state.sorter_running ? "on" : "off"}</span>`);
      pills.push(`<span class="status-pill">camera: ${state.camera_source || "n/a"}</span>`);
      pills.push(`<span class="status-pill">tracker: ${state.tracker_calibrated ? "calibrated" : "calibrating"}</span>`);
      if (state.suggested_red_column !== null) {
        pills.push(`<span class="status-pill">red column: ${state.suggested_red_column}</span>`);
      }
      if (state.detected_yellow_column !== null) {
        pills.push(`<span class="status-pill">yellow column: ${state.detected_yellow_column}</span>`);
      }
      document.getElementById("pills").innerHTML = pills.join("");
    }

    function bannerConfig(state) {
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
          title: `Place RED in column ${state.suggested_red_column ?? "-"}`,
          text: state.prompt || "Drop the red piece on the real board and confirm it here.",
        };
      }
      if (state.game_status === "thinking") {
        return {
          className: "banner thinking",
          title: "Computer is thinking",
          text: state.message || "Choosing where RED should go next.",
        };
      }
      if (state.game_status === "waiting_human_move") {
        return {
          className: "banner ready",
          title: "Your turn",
          text: state.prompt || "Drop a YELLOW piece or enter the column manually.",
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
          title: state.winner === 1 ? "RED wins" : state.winner === 2 ? "YELLOW wins" : "Game finished",
          text: state.message || "Use reset to start a fresh round.",
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
        title.innerHTML = `<span class="thinking">${config.title}</span>`;
      } else {
        title.textContent = config.title;
      }
      text.textContent = config.text;
    }

    function renderMeta(state) {
      document.getElementById("metaStatus").textContent = state.game_status;
      document.getElementById("metaTracker").textContent = state.tracker_calibrated ? "calibrated" : "calibrating";
      document.getElementById("metaCamera").textContent = state.camera_source || "n/a";
      document.getElementById("metaRed").textContent =
        state.suggested_red_column !== null ? state.suggested_red_column : "-";
    }

    function winnerLabel(value) {
      if (value === 1) return "red";
      if (value === 2) return "yellow";
      return "none";
    }

    function renderStateBlocks(state) {
      document.getElementById("stateGameRunning").textContent = state.game_running ? "yes" : "no";
      document.getElementById("stateGamePhase").textContent = state.game_phase || "idle";
      document.getElementById("stateTurnState").textContent = state.turn_state || "idle";
      document.getElementById("stateWinner").textContent = winnerLabel(state.winner);

      document.getElementById("stateSortingEnabled").textContent = state.sorting_enabled ? "yes" : "no";
      document.getElementById("stateSorterRunning").textContent = state.sorter_running ? "running" : "off";
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

    function renderConfirmationCards(state) {
      const yellowCard = document.getElementById("yellowCard");
      const redCard = document.getElementById("redCard");
      const yellowCopy = document.getElementById("yellowCopy");
      const redCopy = document.getElementById("redCopy");

      yellowCard.classList.toggle("hidden", state.awaiting_confirmation !== "yellow");
      redCard.classList.toggle("hidden", state.awaiting_confirmation !== "red");

      if (state.awaiting_confirmation === "yellow") {
        yellowCopy.textContent = state.prompt || "Tap the highlighted yellow slot to confirm it, or tap a different slot to override it.";
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
      renderPills(latestState);
      renderMeta(latestState);
      renderStateBlocks(latestState);
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
