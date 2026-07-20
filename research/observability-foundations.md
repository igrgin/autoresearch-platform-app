# Observability foundations for Battleground

Checked 2026-07-21 against official documentation, specifications, source repositories, and package metadata.

## Executive finding

The V1 architecture decision is no longer simply “custom protocol versus the established heavyweight trackers.” **Trackio is now a credible lightweight substrate candidate and deserves a bounded prototype before the observability contract is locked.** Its current release is local-first, writes to SQLite or append-only JSONL, buffers failed remote delivery locally and replays it, supports arbitrary user metrics and system metrics, stores media and versioned artifacts, exposes HTTP and Python query APIs, and permits a completely custom frontend. These capabilities overlap unusually closely with Battleground’s requirements. Sources: [Trackio overview](https://huggingface.co/docs/trackio/index), [storage modes](https://huggingface.co/docs/trackio/environment_variables), [storage schema](https://huggingface.co/docs/trackio/storage_schema), [artifacts](https://huggingface.co/docs/trackio/artifacts), and [API](https://huggingface.co/docs/trackio/api).

Trackio still cannot replace Battleground’s domain model. Battleground must remain authoritative for Research Project, Research Run, Experiment identity, source commit, accepted lineage, keep/discard/crash verdict, verdict reason, Objective Metric validation, and agent-control state. Trackio calls an individual execution a “run,” has its own lifecycle and mutable database, does not capture Commander’s process truth or Git semantics, and explicitly labels its database schema beta and subject to change. This means the viable Trackio choice is **telemetry substrate behind a Battleground-owned adapter**, not “make Trackio the Experiment Ledger.” [Trackio’s schema stability note](https://huggingface.co/docs/trackio/storage_schema) explicitly warns that future releases may change the schema and require migrations or regenerated databases.

If the prototype rejects Trackio, a small Battleground-owned, versioned JSONL protocol remains the best fallback. OpenTelemetry, MLflow, Aim, and TensorBoard are useful interoperability targets or inputs, but none is a better V1 authority for this product.

## Requirement comparison

“Yes” below means the foundation provides the capability itself; it does not mean that the capability already matches Battleground’s semantics.

| Foundation | Local-first data | Remote/reconnect story | User metrics | Logs | Artifacts/media | Custom UI access | Principal V1 trade-off |
|---|---|---|---|---|---|---|---|
| **Trackio 0.31.x** | SQLite per project; optional per-process JSONL inbox | HTTP self-hosting; failed remote batches persist locally and retry | Yes, arbitrary logged mappings and steps | Alerts and text/media, but not runner-owned raw stdout/stderr | Yes, including offline versioned artifacts and lineage | Documented HTTP/Python APIs and replaceable static frontend | Best capability fit, but beta schema, non-trivial Python dependencies, and a second “run” model |
| **Battleground JSONL** | Exactly as designed | Commander can copy/tail an acknowledged spool over its existing provider channel | Exactly as designed | Runner can frame stdout/stderr independently | Must be designed and built | Exact domain/API fit | Lowest dependency and semantic risk; highest implementation and maintenance burden |
| **MLflow 3.14** | Local SQLite by default | Tracking server REST; no durable client-side offline replay contract was found in the reviewed Tracking APIs | Yes, metric history with timestamps and steps | System metrics; raw process logs still require runner capture | Mature artifact stores | REST API is available, but MLflow also owns a UI and schema | Mature but duplicates Experiment/Run/storage/UI concepts and requires migration management |
| **Aim 3.29.1** | Local `.aim` repository | Dedicated HTTP/WebSocket tracking server | Yes, metric sequences and arbitrary objects | Captures terminal output near real time | File/S3 artifacts | SDK/query language and its own web UI | Strong features, but custom RocksDB storage, another server/UI, and no published Windows wheels in the current release files |
| **TensorBoard 2.21** | Append-only `tfevents` files | Copy/tail files externally; no transport protocol | Scalars, histograms, images, graphs, embeddings | No lifecycle-aware raw process log stream | Visual summaries, not a general artifact ledger | Event readers/plugins exist, but a custom UI would depend on TensorBoard formats | Excellent compatibility input and diagnostic viewer, not an Experiment lifecycle foundation |
| **OpenTelemetry Python 1.44** | No stable Python file-spool foundation; OTLP file exporter spec remains Development | OTLP defines retries; production guidance centers on a Collector/backend | Metrics, traces, logs | Python logs remain Development | No experiment artifact model | Standard protocol and many backends | Best for app/runtime diagnostics and export; semantic mismatch with ordered training history and verdicts |

Package versions are current PyPI releases at the time of checking: [Trackio](https://pypi.org/project/trackio/), [MLflow](https://pypi.org/project/mlflow/), [Aim](https://pypi.org/project/aim/), [TensorBoard](https://pypi.org/project/tensorboard/), and [OpenTelemetry SDK](https://pypi.org/project/opentelemetry-sdk/).

## Trackio: the newly credible lightweight option

### What it already supplies

Trackio describes itself as a lightweight, local-first tracker aimed at humans and ML agents. In local mode it keeps each project in a separate SQLite database, with media and uploaded files beside it. Its `jsonl` storage mode instead lets each training process append fragments under an inbox and lets the dashboard import them into SQLite; `auto` selects that mode on detected network filesystems. This avoids concurrent training processes writing directly to SQLite. Sources: [Trackio overview](https://huggingface.co/docs/trackio/index), [environment variables and storage modes](https://huggingface.co/docs/trackio/environment_variables), and [documented SQLite schema](https://huggingface.co/docs/trackio/storage_schema).

For live remote operation, Trackio can send to a self-hosted HTTP server authenticated with a write token. Its documented client behavior queues log calls in memory, writes failed batches to local SQLite, and replays them when connectivity returns. Its artifact system works offline, uses versioned named bundles, de-duplicates content, records producer/consumer lineage, and syncs to a self-hosted server or Hugging Face Space when configured. Sources: [self-hosted server](https://huggingface.co/docs/trackio/self_hosted_server), [Trackio repository throughput and recovery notes](https://github.com/gradio-app/trackio#throughput--rate-limits), and [artifacts](https://huggingface.co/docs/trackio/artifacts).

For Battleground’s UI, Trackio exposes plain HTTP endpoints, a Python API, read-only SQL through its CLI, and a `frontend_dir` option that replaces the bundled frontend while keeping `/api/*`. That is a much more direct custom-UI path than TensorBoard’s event internals or Aim’s application framework. Sources: [API and MCP server](https://huggingface.co/docs/trackio/api_mcp_server), [CLI queries](https://huggingface.co/docs/trackio/cli_commands), and [`show()` API](https://huggingface.co/docs/trackio/api).

Trackio is cross-platform at the packaging level: the current distribution is an OS-independent `py3-none-any` wheel. It is not standard-library-small, however. Current package metadata lists Brotli, Gradio Client, Hugging Face Hub, NumPy, orjson, Pillow, Starlette, Uvicorn, and multipart support among its runtime dependencies. Source: [Trackio PyPI metadata and files](https://pypi.org/project/trackio/).

### What Battleground would still own

Even with Trackio, Commander must independently capture and preserve:

- command phase, PID, start/end, timeout, signal, and exit code;
- raw stdout and stderr with stream identity;
- provider/SSH failures and transfer failures;
- the association among Research Run, Experiment, scratch source, and Git commit;
- Objective Metric declaration, direction, unit, final-value policy, and validation;
- keep/discard/crash verdict and reason;
- acknowledgement and replay boundaries across Commander’s own control channel.

The first three are process truth and remain available even if `train.py` fails before importing any telemetry library. The rest are Battleground domain facts rather than generic experiment-tracker data.

### Questions the prototype must answer

A bounded Trackio prototype should test the adapter boundary, not build a Battleground screen. It should answer:

1. Can Commander force a stable Battleground-owned Experiment ID and source sequence/deduplication key without depending on a mutable run name?
2. Can a remote job write entirely locally, lose connectivity, finish, and later be imported idempotently through Commander without requiring the GPU host to call back into the desktop?
3. Can Battleground use supported Trackio APIs for live and historical metric reads, or would required queries depend on the explicitly unstable SQLite schema?
4. Can the Trackio runtime be installed reliably in representative Runpod/Hyperstack/Verda Python environments, while Battleground’s desktop remains functional on macOS, Windows, and Linux?
5. Can Battleground preserve unknown metric/media records and migrate them across Trackio upgrades?
6. Does Trackio’s artifact layer help, or does it conflict with Battleground’s Git refs and project-defined retained artifacts?
7. What happens to queued metrics on `SIGKILL`, host loss, or a process that never calls `finish()`?

Failure on stable identity, offline idempotence, supported query access, or cross-platform packaging should reject Trackio as the V1 substrate.

## Why the established alternatives remain secondary

### OpenTelemetry

OpenTelemetry Python currently marks traces and metrics Stable and logs Development. Its standard OTLP path assumes an exporter plus a Collector or backend; the Python documentation explicitly recommends the Collector for production. OTLP specifies exponential-backoff retries for retryable errors and disconnects, but the OTLP file-exporter specification—the closest standardized local spool—is still Development. Sources: [Python status](https://opentelemetry.io/docs/languages/python/), [Python exporters](https://opentelemetry.io/docs/languages/python/exporters/), [OTLP exporter retry specification](https://opentelemetry.io/docs/specs/otel/protocol/exporter/), and [OTLP file exporter](https://opentelemetry.io/docs/specs/otel/protocol/file-exporter/).

More importantly, OpenTelemetry metrics are aggregatable timeseries built around Sum, Gauge, Histogram, and ExponentialHistogram streams. That is useful for GPU utilization and Battleground/Commander operational health, but it does not define an Experiment, Objective Metric, artifact, commit, or keep/discard verdict. [The metrics data model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/) describes the timeseries semantics. OpenTelemetry should therefore be an optional exporter for application diagnostics, not the V1 research ledger or sole training-history format.

### MLflow

MLflow is the mature closest fit: Tracking records runs, metrics, parameters, code versions, tags, system metrics, and artifacts; it supports both local SQLite and a standalone REST tracking server. Sources: [MLflow Tracking](https://mlflow.org/docs/latest/tracking), [Tracking API](https://mlflow.org/docs/latest/ml/tracking/tracking-api/), [system metrics](https://mlflow.org/docs/latest/ml/tracking/system-metrics), and [tracking server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/).

The cost is conceptual and operational duplication. MLflow’s Experiment groups MLflow Runs, while Battleground’s Research Run groups immutable candidate Experiments. Its default database has its own schema and required upgrade procedure, and large artifacts live in a separate artifact store. Sources: [backend stores](https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/) and [upgrade procedure](https://mlflow.org/docs/latest/self-hosting/migration/). The reviewed APIs document local or direct server logging but not Trackio-like durable client-side offline replay, so Commander would still need a remote spool. MLflow is best kept as the first optional export target for users who already operate it.

### Aim

Aim 3 provides rich local tracking, a dedicated HTTP/WebSocket remote server, metric sequences, near-real-time terminal capture, system information, artifacts, and a capable comparison UI. Sources: [overview](https://aimstack.readthedocs.io/en/latest/understanding/overview.html), [remote tracking](https://aimstack.readthedocs.io/en/latest/using/remote_tracking.html), [terminal capture](https://aimstack.readthedocs.io/en/latest/using/configure_runs.html), and [artifacts](https://aimstack.readthedocs.io/en/latest/using/artifacts.html).

It also owns a custom RocksDB-based `.aim` repository and its own server/UI lifecycle. The current `aim` and `aimrocks` release files provide macOS and Linux wheels but no Windows wheel, which is a packaging risk for a cross-platform local application. Sources: [Aim storage](https://aimstack.readthedocs.io/en/latest/understanding/data_storage.html), [Aim release files](https://pypi.org/project/aim/3.29.1/#files), and [aimrocks release files](https://pypi.org/project/aimrocks/0.5.2/#files). Aim remains useful UI inspiration, but Trackio is a cleaner lightweight candidate.

### TensorBoard

TensorBoard’s writers and plugins remain excellent for framework-native diagnostics. Its writers produce append-only `tfevents` files and support scalars, images, histograms, graphs, embeddings, and profiler data. TensorBoard can stitch multiple event files from restarted processes into one execution history. Sources: [TensorBoard repository and event-file concepts](https://github.com/tensorflow/tensorboard) and [PyTorch SummaryWriter](https://docs.pytorch.org/docs/stable/tensorboard.html).

That format has no remote transport, process lifecycle, general artifact ledger, verdict, or Git relationship. V1 should preserve project-produced `tfevents` as diagnostic artifacts and may later import scalar series or launch TensorBoard on demand. It should not use TensorBoard events as Battleground’s canonical telemetry contract.

## Decision boundary exposed by this research

The later architecture decision should compare only these two V1 foundations:

1. **Trackio adapter:** Trackio supplies metric/media/artifact buffering and query infrastructure; Battleground supplies identity mapping, process logs, lifecycle, Git/verdict authority, and the custom desktop UI.
2. **Battleground protocol:** a standard-library instrumentation shim appends a versioned Battleground JSONL envelope; Commander transfers it over the provider channel; Battleground validates and stores it alongside runner-owned logs and ledger facts.

OpenTelemetry, MLflow, Aim, and TensorBoard should not be candidates for the authoritative V1 foundation. They remain explicitly scoped interoperability roles: OTLP export for operational diagnostics, MLflow export first among experiment trackers, Aim import only if user demand appears, and TensorBoard artifact preservation/import.

The critical trade is therefore **reuse versus authority**, not feature count. Trackio removes substantial metric, media, artifact, query, and buffering work, but introduces an evolving external schema and overlapping run model. A Battleground protocol preserves exact semantics and minimal training dependencies, but makes Battleground responsible for every durability, ingestion, migration, query, and artifact feature. The prototype should establish whether Trackio’s supported adapter surface is stable enough to justify that dependency.
