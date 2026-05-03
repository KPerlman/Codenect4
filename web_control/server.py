from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from web_control.controller import RobotWebController


controller = RobotWebController()
app = FastAPI(title="Codenect4 Web Control")
WEB_CONTROL_VERSION = "broadcast-desk-2026-05-03a"


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
      --bg: #09111f;
      --bg-top: #10213d;
      --card: rgba(14, 24, 43, 0.9);
      --card-soft: rgba(16, 29, 52, 0.72);
      --ink: #f4f7fb;
      --muted: #9fb0cb;
      --line: rgba(255,255,255,0.08);
      --line-strong: rgba(255,255,255,0.18);
      --accent: #2b7cff;
      --accent-soft: rgba(43,124,255,0.18);
      --yellow: #f4c542;
      --yellow-soft: rgba(244,197,66,0.16);
      --red: #ef4b3f;
      --red-soft: rgba(239,75,63,0.16);
      --ok: #16b69a;
      --ok-soft: rgba(22,182,154,0.16);
      --board-blue-top: #2358e4;
      --board-blue-bottom: #102a75;
      --slot-empty: #dce6ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(43,124,255,0.18) 0%, transparent 30%),
        radial-gradient(circle at top right, rgba(239,75,63,0.10) 0%, transparent 24%),
        linear-gradient(180deg, var(--bg-top) 0%, var(--bg) 52%, #050b15 100%);
    }
    .wrap {
      max-width: 1220px;
      margin: 0 auto;
      padding: 24px 20px 48px;
    }
    .masthead {
      display: grid;
      gap: 10px;
      margin-bottom: 18px;
    }
    .kicker {
      color: #78a6ff;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-weight: 800;
      font-size: 0.76rem;
    }
    h1 {
      margin: 0;
      font-size: 2.8rem;
      line-height: 0.96;
      letter-spacing: -0.06em;
      font-weight: 820;
    }
    .sub {
      margin: 0;
      color: var(--muted);
      max-width: 42rem;
      line-height: 1.5;
    }
    .layout {
      display: grid;
      gap: 18px;
      align-items: start;
    }
    @media (min-width: 980px) {
      .layout {
        grid-template-columns: minmax(0, 1.45fr) minmax(340px, 0.72fr);
      }
    }
    .stack {
      display: grid;
      gap: 14px;
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 18px 40px rgba(0,0,0,0.22);
      backdrop-filter: blur(12px);
    }
    .hero-panel {
      padding: 0;
      overflow: hidden;
    }
    .broadcast-banner {
      display: grid;
      gap: 0;
    }
    .banner-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      background: rgba(255,255,255,0.05);
      border-bottom: 1px solid var(--line);
    }
    .banner-label {
      font-size: 0.78rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-weight: 800;
      color: #a7c5ff;
    }
    .live-pill {
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--red);
      color: white;
      font-size: 0.75rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .banner-main {
      padding: 18px 18px 16px;
      display: grid;
      gap: 8px;
    }
    .banner-title {
      font-size: 2rem;
      line-height: 0.96;
      letter-spacing: -0.05em;
      font-weight: 810;
    }
    .banner-copy {
      color: var(--muted);
      line-height: 1.5;
      max-width: 48rem;
    }
    .banner-main.thinking {
      background: linear-gradient(180deg, rgba(43,124,255,0.18) 0%, rgba(43,124,255,0.06) 100%);
    }
    .banner-main.waiting {
      background: linear-gradient(180deg, rgba(244,197,66,0.18) 0%, rgba(244,197,66,0.06) 100%);
    }
    .banner-main.ready {
      background: linear-gradient(180deg, rgba(22,182,154,0.16) 0%, rgba(22,182,154,0.05) 100%);
    }
    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line-strong);
      background: rgba(255,255,255,0.05);
      color: #d7e4ff;
      font-size: 0.76rem;
      font-weight: 700;
    }
    .section-title {
      margin: 0 0 12px;
      font-size: 0.82rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: #8fa7d4;
      font-weight: 800;
    }
    .board-card {
      display: grid;
      gap: 12px;
      padding: 18px;
    }
    .cols {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 8px;
      text-align: center;
      color: #8da5d9;
      font-size: 0.74rem;
      font-weight: 800;
      letter-spacing: 0.12em;
    }
    .board {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 12px;
      padding: 22px;
      background:
        radial-gradient(circle at top, rgba(255,255,255,0.12) 0%, transparent 30%),
        linear-gradient(180deg, var(--board-blue-top) 0%, var(--board-blue-bottom) 100%);
      border-radius: 14px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.12), 0 22px 34px rgba(0,0,0,0.28);
    }
    .slot {
      aspect-ratio: 1;
      border-radius: 999px;
      background:
        radial-gradient(circle at 35% 30%, #ffffff 0%, #f3f6ff 24%, var(--slot-empty) 60%, #ccd8f6 100%);
      border: 2px solid rgba(255,255,255,0.14);
      box-shadow: inset 0 6px 12px rgba(0,0,0,0.18);
    }
    .slot.red {
      background: radial-gradient(circle at 35% 30%, #ff9f92 0%, #f65d4b 28%, var(--red) 68%, #971d16 100%);
    }
    .slot.yellow {
      background: radial-gradient(circle at 35% 30%, #fff4aa 0%, #f8df7a 34%, var(--yellow) 72%, #c59015 100%);
    }
    .slot.pending-yellow {
      background: radial-gradient(circle at 35% 30%, #fff9ca 0%, #fff09f 36%, #f7d96e 70%, #d7a92b 100%);
      opacity: 0.84;
      box-shadow: inset 0 4px 10px rgba(120,90,0,0.12), 0 0 0 3px rgba(244,197,66,0.28);
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
      color: var(--muted);
      font-size: 0.82rem;
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
    .legend-dot.empty { background: var(--slot-empty); border: 1px solid #a8badf; }
    .state-grid {
      display: grid;
      gap: 10px;
    }
    .state-box {
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--card-soft);
    }
    .state-box h3 {
      margin: 0 0 8px;
      font-size: 0.74rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: #8fa7d4;
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
    button.warning { background: var(--yellow); color: #271800; }
    button.danger { background: var(--red); }
    button.ok { background: var(--ok); }
    button.secondary { background: #42526f; }
    .confirm-card {
      border-radius: 8px;
      border: 1px solid var(--line-strong);
      background: rgba(255,255,255,0.04);
      padding: 16px;
    }
    .confirm-card.hidden {
      display: none;
    }
    .confirm-title {
      margin: 0 0 8px;
      font-size: 1rem;
      letter-spacing: -0.02em;
    }
    .confirm-copy {
      margin: 0 0 12px;
      color: var(--muted);
      line-height: 1.45;
      font-size: 0.92rem;
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
      <div class="kicker">Live Match Console</div>
      <h1>Connect4 Broadcast Desk</h1>
      <p class="sub">A live control surface for state, move confirmation, sorter control, and real-time game flow.</p>
    </div>

    <div class="layout">
      <div class="stack">
        <div class="panel hero-panel">
          <div class="broadcast-banner">
            <div class="banner-top">
              <div class="banner-label">Game Feed</div>
              <div class="live-pill">Live</div>
            </div>
            <div id="turnBanner" class="banner-main">
              <div id="bannerTitle" class="banner-title">Idle</div>
              <div id="bannerText" class="banner-copy">Start the game loop when you're ready.</div>
            </div>
          </div>
        </div>

        <div class="panel board-card">
          <div class="section-title">Board View</div>
          <div class="cols"><div>6</div><div>5</div><div>4</div><div>3</div><div>2</div><div>1</div><div>0</div></div>
          <div id="board" class="board"></div>
          <div class="legend">
            <div class="legend-chip"><span class="legend-dot yellow"></span><span>Player / Yellow</span></div>
            <div class="legend-chip"><span class="legend-dot red"></span><span>Computer / Red</span></div>
            <div class="legend-chip"><span class="legend-dot empty"></span><span>Empty</span></div>
          </div>
        </div>
      </div>

      <div class="stack">
        <div class="panel">
          <div class="section-title">Live Status</div>
          <div id="pills" class="chip-row"></div>
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
              <h3>Detection</h3>
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
                <div class="state-row"><span>Camera source</span><strong id="stateCameraSource">n/a</strong></div>
                <div class="state-row"><span>Suggested red</span><strong id="metaRed">-</strong></div>
                <div class="state-row"><span>Tracker calibrated</span><strong id="stateTrackerCalibrated">no</strong></div>
              </div>
            </div>
          </div>
        </div>

        <div id="yellowCard" class="panel confirm-card hidden">
          <div class="section-title">Yellow Confirmation</div>
          <div class="confirm-title">Check player move</div>
          <div id="yellowCopy" class="confirm-copy">Tap the highlighted yellow slot to confirm it, or tap another slot in the correct column to override it.</div>
        </div>

        <div id="redCard" class="panel confirm-card hidden">
          <div class="section-title">Red Placement</div>
          <div class="confirm-title">Place the computer piece</div>
          <div id="redCopy" class="confirm-copy">The computer has chosen a red column. Place the piece, then confirm it here.</div>
          <div class="controls">
            <button class="warning" onclick="confirmRed()">Red Piece Placed</button>
          </div>
        </div>

        <div class="panel">
          <div class="section-title">Control Deck</div>
          <div class="controls">
            <button onclick="startGame()">Start Game</button>
            <button class="warning" onclick="resetGame()">Reset Game</button>
            <button class="danger" onclick="stopGame()">Stop Game</button>
          </div>
        </div>

        <div class="panel">
          <div class="section-title">Sorting Desk</div>
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
      pills.push(`<span class="chip">status: ${state.game_status}</span>`);
      pills.push(`<span class="chip">phase: ${state.game_phase || "idle"}</span>`);
      pills.push(`<span class="chip">turn: ${state.turn_state || "idle"}</span>`);
      pills.push(`<span class="chip">sorting: ${state.sorter_running ? "running" : "off"}</span>`);
      pills.push(`<span class="chip">tracker: ${state.tracker_calibrated ? "calibrated" : "calibrating"}</span>`);
      document.getElementById("pills").innerHTML = pills.join("");
    }

    function bannerConfig(state) {
      if (state.awaiting_confirmation === "yellow") {
        return {
          className: "banner-main waiting",
          title: `Yellow move detected in column ${state.detected_yellow_column ?? "-"}`,
          text: state.prompt || "Confirm the detected yellow move or correct it.",
        };
      }
      if (state.awaiting_confirmation === "red") {
        return {
          className: "banner-main waiting",
          title: `Place red in column ${state.suggested_red_column ?? "-"}`,
          text: state.prompt || "Drop the red piece on the real board and confirm it here.",
        };
      }
      if (state.game_status === "thinking") {
        return {
          className: "banner-main thinking",
          title: "Computer is thinking",
          text: state.message || "Choosing where red should go next.",
        };
      }
      if (state.game_status === "waiting_human_move") {
        return {
          className: "banner-main ready",
          title: "Player turn",
          text: state.prompt || "Drop a yellow piece and hold the board steady.",
        };
      }
      if (state.game_status === "calibrating") {
        return {
          className: "banner-main",
          title: "Calibrating board",
          text: state.message || "Keep the board visible and empty for a moment.",
        };
      }
      if (state.game_status === "finished") {
        return {
          className: "banner-main ready",
          title: state.winner === 1 ? "Red wins" : state.winner === 2 ? "Yellow wins" : "Game finished",
          text: state.message || "Reset when you're ready for the next round.",
        };
      }
      if (state.game_status === "error") {
        return {
          className: "banner-main waiting",
          title: "Something needs attention",
          text: state.error || state.message || "Check the service logs and current hardware state.",
        };
      }
      return {
        className: "banner-main",
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
