from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from web_control.controller import RobotWebController


controller = RobotWebController()
app = FastAPI(title="Codenect4 Web Control")


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
      --bg: #f2efe6;
      --card: #fffaf2;
      --ink: #1c2b2d;
      --accent: #2f6fed;
      --warn: #d97706;
      --danger: #b42318;
      --ok: #166534;
      --line: #d9d2c2;
      --red: #d92d20;
      --yellow: #f5c518;
    }
    body {
      margin: 0;
      font-family: "Trebuchet MS", "Avenir Next", sans-serif;
      background: linear-gradient(180deg, #e8f1f5 0%, var(--bg) 45%, #efe5cf 100%);
      color: var(--ink);
    }
    .wrap {
      max-width: 860px;
      margin: 0 auto;
      padding: 20px 16px 48px;
    }
    .hero {
      background: radial-gradient(circle at top left, #ffffff 0%, #f7ebd3 60%, #f0dcc0 100%);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 18px;
      box-shadow: 0 18px 40px rgba(31, 41, 55, 0.08);
    }
    h1 {
      margin: 0 0 6px;
      font-size: 1.8rem;
    }
    .sub {
      margin: 0;
      opacity: 0.8;
    }
    .grid {
      display: grid;
      gap: 16px;
      margin-top: 16px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px;
      box-shadow: 0 10px 24px rgba(31, 41, 55, 0.06);
    }
    .controls {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    }
    button {
      border: 0;
      border-radius: 14px;
      padding: 12px 14px;
      font: inherit;
      background: var(--accent);
      color: white;
      cursor: pointer;
    }
    button.secondary { background: #475467; }
    button.warning { background: var(--warn); }
    button.danger { background: var(--danger); }
    button.ok { background: var(--ok); }
    .status-pill {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: #dbe8ff;
      color: #14336b;
      font-size: 0.9rem;
      margin-right: 8px;
      margin-bottom: 8px;
    }
    .board {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 8px;
      margin-top: 12px;
      background: linear-gradient(180deg, #2c5cc5 0%, #173b87 100%);
      padding: 14px;
      border-radius: 22px;
    }
    .slot {
      aspect-ratio: 1;
      border-radius: 999px;
      background: #eef2ff;
      border: 2px solid rgba(255,255,255,0.25);
    }
    .slot.red { background: var(--red); }
    .slot.yellow { background: var(--yellow); }
    .cols {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 8px;
      margin-top: 10px;
      text-align: center;
      font-weight: 700;
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
      border: 1px solid var(--line);
      padding: 10px 12px;
      font: inherit;
      margin-top: 8px;
    }
    .muted {
      opacity: 0.78;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Codenect4 Control</h1>
      <p class="sub">Phone-friendly control surface for the Pi. SSH still works as your fallback path.</p>
    </div>

    <div class="grid">
      <div class="card">
        <div id="pills"></div>
        <div id="message"></div>
        <div id="prompt" style="margin-top: 10px; font-weight: 700;"></div>
      </div>

      <div class="card">
        <h2>Game</h2>
        <div class="controls">
          <button onclick="startGame()">Start Game</button>
          <button class="warning" onclick="resetGame()">Reset Game</button>
          <button class="danger" onclick="stopGame()">Stop Game</button>
        </div>
      </div>

      <div class="card">
        <h2>Sorting</h2>
        <div class="controls">
          <button class="ok" onclick="enableSorting()">Enable Sorting</button>
          <button class="secondary" onclick="disableSorting()">Disable Sorting</button>
        </div>
      </div>

      <div class="card">
        <h2>Board</h2>
        <div class="cols"><div>6</div><div>5</div><div>4</div><div>3</div><div>2</div><div>1</div><div>0</div></div>
        <div id="board" class="board"></div>
      </div>

      <div class="card">
        <h2>Actions</h2>
        <div class="controls">
          <button class="ok" onclick="confirmYellow(true)">Confirm Yellow</button>
          <button class="warning" onclick="confirmRed()">Confirm Red Placed</button>
        </div>
        <label class="muted" for="manualCol">Manual / corrected human column</label>
        <input id="manualCol" type="number" min="0" max="6" placeholder="0-6">
        <div class="controls" style="margin-top:10px;">
          <button onclick="sendManualHuman()">Submit Human Column</button>
          <button class="secondary" onclick="correctYellow()">Correct Yellow Detection</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let latestState = null;

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

    async function correctYellow() {
      const val = Number(document.getElementById("manualCol").value);
      if (Number.isNaN(val)) return;
      await api("/api/game/yellow-confirm", "POST", { accept: false, column: val });
      await refresh();
    }

    async function confirmRed() {
      await api("/api/game/red-confirm", "POST");
      await refresh();
    }

    async function sendManualHuman() {
      const val = Number(document.getElementById("manualCol").value);
      if (Number.isNaN(val)) return;
      await api("/api/game/manual-human", "POST", { column: val });
      await refresh();
    }

    function renderBoard(board) {
      const root = document.getElementById("board");
      root.innerHTML = "";
      if (!board) return;
      const mirrored = board.map(row => [...row].reverse());
      for (const row of mirrored) {
        for (const cell of row) {
          const slot = document.createElement("div");
          slot.className = "slot";
          if (cell === 1) slot.classList.add("red");
          if (cell === 2) slot.classList.add("yellow");
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

    function renderText(state) {
      const msg = document.getElementById("message");
      const prompt = document.getElementById("prompt");
      const thinkingClass = state.game_status === "thinking" ? "thinking" : "";
      msg.innerHTML = `<strong class="${thinkingClass}">${state.message || ""}</strong>${state.error ? `<div style="color:#b42318; margin-top:8px;">${state.error}</div>` : ""}`;
      prompt.textContent = state.prompt || "";
    }

    async function refresh() {
      latestState = await api("/api/state");
      renderPills(latestState);
      renderBoard(latestState.current_board);
      renderText(latestState);
    }

    refresh();
    setInterval(refresh, 800);
  </script>
</body>
</html>
"""
