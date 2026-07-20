const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const protocol = "battleground.commander/1";
const state = {
  protocol,
  supervisor: "stopped",
  sidecarPid: null,
  lastAction: "application loaded",
  lastSequence: null,
  ordered: true,
  frames: [],
  stderr: [],
  errors: [],
};

let nextRequest = 1;
const stateElement = document.querySelector("#state");

function render() {
  stateElement.textContent = JSON.stringify(state, null, 2);
  const running = ["starting", "ready", "running"].includes(state.supervisor);
  document.querySelector('[data-action="start"]').disabled = running;
  for (const action of ["ping", "stream", "shutdown", "crash", "kill"]) {
    document.querySelector(`[data-action="${action}"]`).disabled = !running;
  }
}

function recordError(error) {
  state.errors.push(String(error));
  state.lastAction = "error";
  render();
}

function request(op, payload = {}) {
  const id = `ui-${nextRequest++}`;
  state.lastAction = `request ${op} (${id})`;
  render();
  return invoke("commander_send", { request: { id, op, payload } });
}

await listen("commander-frame", ({ payload }) => {
  let frame;
  try {
    frame = JSON.parse(payload);
  } catch (error) {
    recordError(`non-JSON stdout: ${payload}; ${error}`);
    return;
  }

  if (frame.protocol !== protocol) {
    state.errors.push(`protocol mismatch: ${frame.protocol}`);
  }
  if (state.lastSequence !== null && frame.seq !== state.lastSequence + 1) {
    state.ordered = false;
    state.errors.push(`sequence gap: ${state.lastSequence} -> ${frame.seq}`);
  }
  state.lastSequence = frame.seq;
  state.frames.push(frame);
  if (frame.kind === "hello") {
    state.supervisor = "ready";
    state.sidecarPid = frame.pid;
  }
  render();
});

await listen("commander-lifecycle", ({ payload }) => {
  state.lastAction = payload.kind;
  if (payload.kind === "started") {
    state.supervisor = "starting";
    state.lastSequence = null;
    state.ordered = true;
    state.frames = [];
    state.stderr = [];
  } else if (payload.kind === "stderr") {
    state.stderr.push(payload.detail);
  } else if (payload.kind === "exited") {
    state.supervisor = "stopped";
    state.sidecarPid = null;
  }
  render();
});

document.querySelector("nav").addEventListener("click", async (event) => {
  const action = event.target.dataset.action;
  if (!action) return;

  try {
    if (action === "start") {
      state.lastAction = "start requested";
      render();
      await invoke("commander_start");
    } else if (action === "kill") {
      state.lastAction = "force kill requested";
      render();
      await invoke("commander_kill");
    } else {
      await request(action, action === "stream" ? { count: 5 } : {});
    }
  } catch (error) {
    recordError(error);
  }
});

render();
