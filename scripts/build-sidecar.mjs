import { execFileSync } from "node:child_process";
import { chmodSync, copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const windows = process.platform === "win32";
const venv = join(root, ".prototype-venv");
const systemPython = process.env.PYTHON
  ? { command: process.env.PYTHON, args: [] }
  : windows
    ? { command: "py", args: ["-3"] }
    : { command: "python3", args: [] };

function run(command, args, options = {}) {
  execFileSync(command, args, { cwd: root, stdio: "inherit", ...options });
}

const venvPython = windows
  ? join(venv, "Scripts", "python.exe")
  : join(venv, "bin", "python");

if (!existsSync(venvPython)) {
  run(systemPython.command, [...systemPython.args, "-m", "venv", venv]);
}

run(venvPython, [
  "-m",
  "pip",
  "install",
  "--disable-pip-version-check",
  "pyinstaller>=6,<7",
]);

run(venvPython, [
  "-m",
  "PyInstaller",
  "--clean",
  "--noconfirm",
  "--onefile",
  "--name",
  "battleground-commander",
  "--distpath",
  join(root, ".prototype-dist"),
  "--workpath",
  join(root, ".prototype-build", "work"),
  "--specpath",
  join(root, ".prototype-build"),
  join(root, "commander", "commander.py"),
]);

const rustDetails = execFileSync("rustc", ["-Vv"], { encoding: "utf8" });
const target = rustDetails.match(/^host:\s+(.+)$/m)?.[1];
if (!target) throw new Error("Could not determine the Rust host target triple");

const extension = windows ? ".exe" : "";
const source = join(root, ".prototype-dist", `battleground-commander${extension}`);
const binaries = join(root, "src-tauri", "binaries");
const destination = join(
  binaries,
  `battleground-commander-${target}${extension}`,
);
mkdirSync(binaries, { recursive: true });
copyFileSync(source, destination);
if (!windows) chmodSync(destination, 0o755);
console.log(`Prepared ${destination}`);
