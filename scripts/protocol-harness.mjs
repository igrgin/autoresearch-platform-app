import { spawn, execFileSync } from "node:child_process";
import { createInterface } from "node:readline";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const target = execFileSync("rustc", ["-Vv"], { encoding: "utf8" }).match(
  /^host:\s+(.+)$/m,
)?.[1];
const extension = process.platform === "win32" ? ".exe" : "";
const executable = join(
  root,
  "src-tauri",
  "binaries",
  `battleground-commander-${target}${extension}`,
);
const child = spawn(executable, ["serve", "--stdio"], {
  stdio: ["pipe", "pipe", "inherit"],
});
const lines = createInterface({ input: child.stdout });
const frames = [];
const protocol = "battleground.commander/1";

function send(id, op, payload = {}) {
  child.stdin.write(`${JSON.stringify({ protocol, id, op, payload })}\n`);
}

function waitFor(predicate, timeout = 5000) {
  return new Promise((resolveFrame, reject) => {
    const timer = setTimeout(() => reject(new Error("protocol timeout")), timeout);
    const onLine = (line) => {
      const frame = JSON.parse(line);
      frames.push(frame);
      if (predicate(frame)) {
        clearTimeout(timer);
        lines.off("line", onLine);
        resolveFrame(frame);
      }
    };
    lines.on("line", onLine);
  });
}

await waitFor((frame) => frame.kind === "hello");
send("harness-ping", "ping");
await waitFor((frame) => frame.id === "harness-ping" && frame.ok === true);
send("harness-stream", "stream", { count: 5 });
await waitFor(
  (frame) => frame.kind === "event" && frame.data?.index === frame.data?.total,
);
send("harness-shutdown", "shutdown");
await waitFor((frame) => frame.id === "harness-shutdown" && frame.ok === true);

const exitCode = await new Promise((resolveExit) => child.on("exit", resolveExit));
const ordered = frames.every((frame, index) => {
  return frame.protocol === protocol && frame.seq === index;
});
if (exitCode !== 0 || !ordered) {
  throw new Error(`protocol failed: exit=${exitCode}, ordered=${ordered}`);
}
console.log(
  `Protocol verified: ${frames.length} ordered frames, graceful exit ${exitCode}.`,
);
