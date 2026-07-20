# Trackio telemetry-substrate prototype

**PROTOTYPE — throw this branch away after the decision.**

This terminal prototype asks whether Trackio 0.31.5 can sit beneath Battleground
without taking ownership of the Experiment lifecycle. It exercises four gates:

1. stable Battleground Experiment identity across Trackio resume and duplicate names;
2. idempotent replay after a lost response and durable replay after a disconnected process exits;
3. supported programmatic metric queries without depending on an undocumented database layout; and
4. binary-wheel resolution for Windows, macOS, and Linux.

Run it from the repository root:

```sh
./prototypes/trackio-telemetry-substrate/run.sh
```

Press `a` to run every probe. All data and both simulated client/server stores
live in temporary directories. The replay probe starts a local Trackio server,
injects one lost response, stops the server, finishes a disconnected run, then
restarts the server to see whether a later client replays the durable row.

The fault injector reaches into Trackio private state solely to create the lost
response after the server has committed. That private state is not part of the
proposed integration.

## Candidate interpretation

Trackio is a credible secondary telemetry store, but it does not eliminate the
need for Battleground's own durable transport. In 0.31.5, generated `log_id`s
make same-process retries idempotent. A self-hosted `server_url` client also
persists a failed batch locally when it exits, but a later connected client does
not automatically re-arm those pending rows. The Hugging Face `space_id` path
does re-arm them, but a hosted control plane is outside Battleground V1.

Stable identity is workable only if the Experiment Ledger owns the Battleground
Experiment ID and stores the generated Trackio `run_id`; `trackio.init()` does
not accept a caller-supplied run ID and duplicate run names are legal. Queries
are available through supported CLI and HTTP surfaces, while direct SQLite
coupling remains risky because Trackio labels the schema beta.

The full runtime probe has been executed on macOS arm64. Target-aware dependency
resolution finds binary wheels for Windows x86_64, macOS x86_64/arm64, and Linux
x86_64/arm64; native Windows and Linux runtime smoke tests remain an implementation
prerequisite rather than a decision blocker for this prototype.

The candidate decision is therefore: keep a Battleground-owned append-only
spool and acknowledgement cursor for V1. Treat Trackio as an optional exporter
or derived view, not the required telemetry substrate or lifecycle authority.
