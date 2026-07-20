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

Trackio is viable as a bounded telemetry substrate under Battleground's Control
Lease model. In 0.31.5, generated `log_id`s make retries during the 30-second
reconnection window idempotent. If the lease expires, Commander fails the current
Experiment, leaves the accepted code unchanged, and pauses the Research Run.
Trackio retains the failed Experiment's local telemetry for later diagnosis.

A later self-hosted `server_url` client does not automatically upload those
pending rows. That is no longer a correctness requirement: the failed Experiment
is never resumed or accepted, and Commander can collect its locally queryable
logs after reconnection. Any retry is a new Experiment with a new identity.

Stable identity is workable only if the Experiment Ledger owns the Battleground
Experiment ID and stores the generated Trackio `run_id`; `trackio.init()` does
not accept a caller-supplied run ID and duplicate run names are legal. Queries
are available through supported CLI and HTTP surfaces, while direct SQLite
coupling remains risky because Trackio labels the schema beta.

The full runtime probe has been executed on macOS arm64. Target-aware dependency
resolution finds binary wheels for Windows x86_64, macOS x86_64/arm64, and Linux
x86_64/arm64; native Windows and Linux runtime smoke tests remain an implementation
prerequisite rather than a decision blocker for this prototype.

The candidate decision is therefore: Trackio 0.31.5 can be the V1 telemetry
substrate behind a narrow adapter, provided Battleground remains authoritative
for Experiment identity, Control Leases, failure, Git lineage, Objective Metric
validation, and keep/discard decisions. Pin Trackio's version, persist its generated
`run_id` in the Experiment Ledger, and query through supported CLI/HTTP surfaces.
