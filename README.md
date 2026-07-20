# PROTOTYPE — Tauri + supervised Commander sidecar

This throwaway prototype answers one question: can a minimal Tauri 2 shell bundle, launch, communicate with, supervise, terminate, and package a frozen Python Commander through a versioned stdio protocol?

It deliberately exposes the lifecycle state instead of resembling the eventual Battleground UI. The renderer can invoke only four narrow Rust commands. Rust owns the child process and protocol envelope; the Python executable owns Commander behavior.

## Run it

Prerequisites: current Node.js, Rust stable, and Python 3.10+.

```sh
npm install
npm run prototype
```

`npm run prototype` freezes Commander for the host target and launches Tauri. In the window, exercise start, ping, ordered telemetry, unexpected crash, graceful shutdown, force kill, and restart. The complete observed state is rendered after every action.

The headless protocol check is:

```sh
npm run prototype:verify-protocol
```

The native package build for the current OS is:

```sh
npm run prototype:package
```

The active `.github/workflows/prototype-tauri-sidecar.yml` workflow packages and updater-signs on macOS, Windows, and Linux with disposable prototype keys. Production release jobs must instead share one protected offline-generated key.

## Protocol under test

- Transport: one JSON object per UTF-8 line on stdin/stdout; diagnostics only on stderr.
- Protocol identity: `battleground.commander/1` in every frame.
- Handshake: Commander emits `hello` before accepting requests.
- Correlation: every response echoes the request `id`.
- Ordering: every Commander output frame carries a strictly increasing `seq`.
- Lifecycle: Rust reports started, stderr, protocol frames, and termination separately.
- Authority: the renderer has no shell-plugin, filesystem, or general process permission.

## Deliberate limits

- The Commander executable is a tiny PyInstaller-frozen protocol fixture, not application code.
- The macOS updater artifact is signed with a disposable prototype key. The Windows/Linux workflow is the remaining verification gate. Production identity signing/notarization still requires Apple and Windows credentials; production updater signing requires one offline Tauri key shared by all release jobs.
- The prototype tests child supervision while Battleground is open. Whether a Research Run may outlive Battleground is a separate product decision.
- No persistence, retry/replay, provider, SSH, Git, or Experiment behavior is implemented here.

The concrete production credential and release boundary is documented in `docs/release-path.md`.
