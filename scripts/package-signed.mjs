import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
} from "node:fs";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const tauri = join(root, "node_modules", "@tauri-apps", "cli", "tauri.js");
const secrets = join(root, ".prototype-secrets");
const privateKey = join(secrets, "updater.key");
const publicKey = `${privateKey}.pub`;

function run(command, args, options = {}) {
  execFileSync(command, args, { cwd: root, stdio: "inherit", ...options });
}

mkdirSync(secrets, { recursive: true });
if (!existsSync(privateKey) || !existsSync(publicKey)) {
  run(process.execPath, [
    tauri,
    "signer",
    "generate",
    "--write-keys",
    privateKey,
    "--password",
    "prototype",
    "--force",
    "--ci",
  ]);
}

const configOverride = JSON.stringify({
  bundle: { createUpdaterArtifacts: true },
  plugins: {
    updater: { pubkey: readFileSync(publicKey, "utf8").trim() },
  },
});

run(
  process.execPath,
  [tauri, "build", "--config", configOverride, ...process.argv.slice(2)],
  {
    env: {
      ...process.env,
      TAURI_SIGNING_PRIVATE_KEY: privateKey,
      TAURI_SIGNING_PRIVATE_KEY_PATH: privateKey,
      TAURI_SIGNING_PRIVATE_KEY_PASSWORD: "prototype",
    },
  },
);

function findSignatures(directory) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return findSignatures(path);
    return entry.name.endsWith(".sig") ? [path] : [];
  });
}

const signatures = findSignatures(join(root, "src-tauri", "target", "release", "bundle"));
if (signatures.length === 0) {
  throw new Error("Tauri produced no signed updater artifact");
}
console.log(`Signed updater artifacts:\n${signatures.join("\n")}`);
