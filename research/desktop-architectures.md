# Cross-platform desktop architecture options

Research date: 2026-07-21

## Question

Which current desktop application architecture can support Battleground on macOS, Windows, and Linux while integrating local Git, Python tooling, long-running subprocesses, SSH, secure credentials, live telemetry, packaging, and automatic updates?

## Conclusion

**Use Tauri 2 for the Battleground desktop shell, a web frontend for the UI, and a bundled Python Commander executable as a supervised sidecar.** The installed `battleground-commander` executable should expose both the human-facing CLI and a machine-facing, versioned `serve --stdio` mode. The application and CLI can then share one Python implementation of Git, SSH, provider, experiment, and telemetry behavior instead of maintaining equivalent logic in Rust and Python.

Tauri is not uniquely capable of running the workload. Electron and PySide6 can both do it. Tauri is the best fit because it combines:

- an officially documented way to bundle and stream I/O from a Python sidecar;
- a narrowly permissioned boundary between the web UI and privileged operations;
- ordered channels suitable for live log and metric streams;
- first-party installers and a signed updater path on all three target operating systems; and
- a web UI ecosystem well suited to dense experiment ledgers, diffs, charts, and logs.

The main cost is a three-language application boundary—TypeScript, a small Rust host, and Python—and platform-specific WebView testing. Keep that cost contained: Rust should supervise and bridge Commander, manage application lifecycle, and integrate Tauri facilities; it should not duplicate Battleground's domain model.

## Compared architectures

| Requirement | Tauri 2 + Python sidecar | Electron + Python child | PySide6 / Qt for Python |
| --- | --- | --- | --- |
| macOS, Windows, Linux | Yes; desktop targets are first-class, using each OS's WebView | Yes; Electron publishes binaries for `darwin`, `win32`, and `linux` | Yes; Qt for Python targets all three desktop platforms |
| Git and Python integration | Commander sidecar owns both | Python child can own both; Node could also invoke Git | Native fit: application is already Python |
| Long-running subprocesses | Sidecar spawn, stdin/stdout, exit, and kill are supported; lifecycle durability must be designed above the shell | Node `child_process.spawn()` is asynchronous and stream-based; lifecycle durability must still be designed | `QProcess` exposes asynchronous state, stdout, stderr, exit, crash, and error signals |
| SSH | Commander uses a Python SSH library or the user's OpenSSH client | Same; alternatively Node can own SSH | Direct Python library or OpenSSH integration |
| Live telemetry | Sidecar stdout to Rust, then ordered Tauri channels to the UI | Child streams to main process, then typed IPC to renderer | Qt signals/slots or models update the UI directly |
| Credential support | Official Stronghold encrypted vault; OS keychain access still needs an explicit library/policy | Built-in `safeStorage` uses OS cryptography, with a Linux fallback that must be detected | Python `keyring` supports common OS stores; Linux backend availability must be handled |
| Packaging | First-party bundler supports installers/packages; sidecar binary is bundled per target | Electron Forge creates platform distributables and can include a Python binary | `pyside6-deploy` freezes with Nuitka; installer work is more pieced together |
| Automatic updates | First-party updater creates signed artifacts for Linux, macOS, and Windows | Built-in updater supports macOS and Windows, not Linux | No integrated updater in Qt for Python's deployment tools |
| UI development | Web frontend; broad component/chart/diff ecosystem | Same, with one bundled Chromium version everywhere | Qt Widgets or Qt Quick/QML; capable, but a separate UI ecosystem |
| Important liability | Rust/toolchain and target-specific sidecar builds; system WebViews differ | Largest runtime and attack/dependency surface; Linux update gap | Release engineering and updater gap; QML or native-widget UI specialization |

## Option 1: Tauri 2 with Commander as a Python sidecar

### Why it fits

Tauri explicitly supports bundling an external executable written in any language and identifies Python CLIs or API servers packaged with PyInstaller as a common sidecar use case. Its sidecar API can spawn that executable, read stdout events, write stdin, and constrain which binary and arguments the frontend may invoke. This is an unusually direct match for Commander. [Tauri: Embedding External Binaries](https://v2.tauri.app/develop/sidecar/)

The recommended process boundary is:

```text
Battleground web UI
        |
        | typed Tauri commands and ordered channels
        v
small Tauri/Rust host
        |
        | versioned request/response and event frames over stdio
        v
battleground-commander serve --stdio
        |
        +-- local Git and project files
        +-- Python environments and subprocesses
        +-- SSH / SFTP and provider APIs
        +-- durable telemetry and logs
```

Tauri's ordinary event bus is intended for small event volumes, while its channels are explicitly optimized for fast, ordered streaming and are used internally for child-process output. Use channels for logs, metrics, progress, and lifecycle events; use commands for bounded request/response operations. [Tauri: Calling the Frontend from Rust](https://v2.tauri.app/develop/calling-frontend/)

Tauri's capabilities system can restrict which windows may access privileged commands, and the shell plugin blocks dangerous commands and scopes unless they are enabled. The UI should not receive general shell, filesystem, or secret access. It should receive a narrow Battleground command surface implemented in Rust and Commander. [Tauri: Capabilities](https://v2.tauri.app/security/capabilities/) [Tauri: Shell plugin](https://v2.tauri.app/plugin/shell/)

For distribution, Tauri's CLI produces platform bundles including Linux packages/AppImage, macOS app/DMG, and Windows MSI/NSIS installers. Builds and signing remain platform-specific; for example, MSI creation requires Windows, and macOS distribution requires signing and notarization. [Tauri: Distribution](https://v2.tauri.app/distribute/) [Tauri: Windows Installer](https://v2.tauri.app/distribute/windows-installer/)

The updater is the clearest advantage over the alternatives. It generates signed updater artifacts for Linux AppImage, macOS app bundles, and Windows MSI/NSIS, and can read a static manifest hosted with GitHub Releases. [Tauri: Updater](https://v2.tauri.app/plugin/updater/)

### Credential design

Tauri's official Stronghold plugin stores secrets and keys in an encrypted database on Windows, Linux, and macOS. It is not, by itself, the native OS credential store. [Tauri: Stronghold](https://v2.tauri.app/plugin/stronghold/)

For Battleground, use this policy:

1. Prefer the user's existing SSH agent and OpenSSH files; do not copy private SSH keys into Battleground.
2. Store provider API tokens through Commander using Python `keyring`, which supports macOS Keychain, Windows Credential Locker, Freedesktop Secret Service, and KWallet. [Python keyring documentation](https://keyring.readthedocs.io/en/latest/)
3. Detect and clearly reject an unavailable or insecure Linux keyring backend rather than silently storing plaintext.
4. Pass any short-lived secret between the desktop host and Commander over inherited pipes, never command-line arguments or telemetry.

This keeps credential lookup consistent between the UI and the standalone Commander CLI. Stronghold remains available if a later decision requires a Battleground-specific encrypted vault.

### Costs and risks

- Tauri uses the OS WebView instead of bundling one: WebView2 on Windows and WebKitGTK on Linux are explicit prerequisites. This reduces the bundled browser footprint but requires UI testing against different engines and Linux distributions. [Tauri: Security and system WebViews](https://v2.tauri.app/security/) [Tauri: Prerequisites](https://v2.tauri.app/start/prerequisites/)
- The Python executable must be frozen and built for every supported OS/architecture, named as a target-specific Tauri sidecar, signed as part of the application, and upgraded atomically with it.
- GUI applications on macOS and Linux do not inherit shell-dotfile `PATH` values. Git, Python, and SSH discovery must therefore be explicit and diagnostic rather than assuming an interactive shell environment. [Tauri: macOS Application Bundle](https://v2.tauri.app/distribute/macos-application-bundle/)
- A child sidecar alone does not define what happens when the window or application exits. Battleground still needs a lifecycle decision: either forbid closing while a local job must remain attached, or hand durable work to a separately supervised Commander worker. Remote GPU training should be reconnectable from persisted provider/run identity regardless of UI process lifetime.

## Option 2: Electron with a Python child process

Electron is fully capable and is the strongest fallback if consistent rendering or team familiarity with Electron becomes more valuable than footprint and updater uniformity.

Electron provides separate main and renderer processes, and its utility processes can host Node workloads with message ports. A Python Commander process would instead be spawned from the main process using Node's `child_process.spawn()`, whose asynchronous events and stdin/stdout/stderr pipes support long-lived streaming processes. [Electron: Process Model](https://www.electronjs.org/docs/latest/tutorial/process-model) [Node.js: Child Process](https://nodejs.org/api/child_process.html)

The renderer must stay unprivileged. Electron recommends context isolation, renderer sandboxing, no Node integration for remote content, validated IPC senders, and tightly filtered preload APIs. That is workable, but Electron's own security guide emphasizes that shipping Chromium, Node, npm dependencies, and powerful local APIs expands the responsibility of the application. [Electron: Security](https://www.electronjs.org/docs/latest/tutorial/security) [Electron: Context Isolation](https://www.electronjs.org/docs/latest/tutorial/context-isolation)

Electron's `safeStorage` integrates OS cryptography: Keychain on macOS, DPAPI on Windows, and desktop keyring providers on Linux. Linux may select `basic_text` when the environment or password store is not recognized, so Battleground would have to inspect and reject that backend for provider tokens. [Electron: safeStorage](https://www.electronjs.org/docs/latest/api/safe-storage)

Electron Forge is the recommended packaging path and creates OS-specific distributables, but it is separate tooling rather than part of Electron core. Electron's built-in `autoUpdater` supports macOS and Windows only; its documentation recommends Linux distribution package managers instead. That is a material mismatch for one self-updating personal application distributed from GitHub Releases across all three systems. [Electron: Packaging](https://www.electronjs.org/docs/latest/tutorial/tutorial-packaging) [Electron: autoUpdater](https://www.electronjs.org/docs/latest/api/auto-updater/)

Electron's bundled Chromium gives more consistent rendering across platforms and its ecosystem is mature. Choose it over Tauri if an early UI prototype exposes unacceptable system-WebView differences or if Tauri's Rust and sidecar release pipeline proves materially harder in a packaging spike.

## Option 3: PySide6 / Qt for Python

PySide6 is the credible Python-native option. It is the official Qt binding, supports Windows, Linux, and macOS, and is available under LGPLv3/GPLv3 or a commercial Qt license. [Qt for Python](https://doc.qt.io/qtforpython-6/)

It has the cleanest runtime integration. Git, provider clients, SSH, persistence, and Commander could all live in the same Python process or package. `QProcess` is cross-platform and exposes asynchronous signals for process start, state, stdout, stderr, normal exit, crashes, and errors. Waiting synchronously on the GUI thread can freeze the UI, so all execution must use Qt's asynchronous signals or worker threads. [Qt: QProcess](https://doc.qt.io/qt-6/qprocess.html)

Paramiko provides a Python SSH client with SSH-agent/key-file discovery, host-key verification, remote command streams, and SFTP. It is viable with any of the three desktop shells because Commander remains Python, but PySide has no language boundary around it. [Paramiko: SSHClient](https://docs.paramiko.org/en/stable/api/client.html)

Qt Widgets and Qt Quick/QML can build the required UI, and Qt has native charting, model/view, networking, and threading facilities. The tradeoff is that the project's data-heavy visual interface would be developed in the Qt/QML ecosystem rather than the web ecosystem.

The decisive weakness is delivery. Qt's `pyside6-deploy` wraps Nuitka and can produce executables for all three target platforms. Qt's own deployment guide says the packaging tools need additional resource/metadata hooks and do not provide an application update mechanism. A separate installer and updater system would therefore become product infrastructure. [Qt for Python: pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) [Qt for Python: Deployment](https://doc.qt.io/qtforpython-6/deployment/)

Choose PySide6 only if maintaining one primary language is more important than the web UI ecosystem and a unified signed-update path. It is not a weak framework; it is a weaker fit for this application's desired presentation and release experience.

## Options screened out

- **Flutter** and **Avalonia** are credible cross-platform UI frameworks, but each adds a non-Python application stack and still needs a Python/Commander process boundary. Neither removes a requirement that Tauri already solves more directly.
- **BeeWare/Toga, Flet, pywebview, and similar Python-first approaches** can ship desktop applications, but they do not improve on PySide6's maturity for process control while inheriting equal or greater packaging, platform-integration, or update work. They do not warrant a separate finalist slot.
- **A local web server opened in the user's browser** would simplify UI code but would not provide a cohesive desktop install, credential boundary, lifecycle owner, or automatic-update experience. It also conflicts with the explicit local-application direction.

## Recommended constraints for the later architecture decision

If Tauri is selected, lock these constraints into the specification:

1. **Commander owns domain and execution behavior.** The Rust host does not implement a second experiment, Git, provider, or telemetry model.
2. **Use a private, versioned stdio protocol.** Do not expose an unauthenticated localhost HTTP server merely to connect the UI to Commander.
3. **The renderer has no general shell or filesystem authority.** All privileged operations are narrowly typed and validated across the Tauri boundary.
4. **Telemetry is durable before it is live.** Commander writes logs and metrics to durable local storage; UI channels are a projection that may disconnect and replay.
5. **Build and test on all three operating systems in CI.** A release contains matching signed Battleground and Commander binaries for each target.
6. **Treat updates as atomic.** The desktop shell, protocol version, and bundled Commander update together.
7. **Do an early packaging spike.** Before broad UI implementation, prove installation, sidecar launch, Git/Python/SSH discovery, credential-store behavior, streaming output, signing, and update artifacts on macOS, Windows, and Linux.

## Resolution gist

Tauri 2 plus a bundled Commander Python sidecar is the strongest architecture for Battleground. Electron remains a sound fallback if consistent Chromium rendering outweighs its footprint and Linux updater gap. PySide6 is operationally natural but pushes too much risk into UI specialization and application delivery. The final architecture decision should be gated by a small cross-platform packaging and sidecar spike, not by another broad framework survey.
