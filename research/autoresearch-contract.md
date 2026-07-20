# Karpathy AutoResearch behavioral contract for Battleground V1

Research date: 2026-07-21

## Decision

Battleground should preserve AutoResearch's **scientific loop**, not its incidental shell-and-Git implementation.

The V1 contract should preserve a baseline-first sequence of bounded code changes, evaluation against a frozen harness under a fixed execution profile and budget, one declared Objective Metric, and an explicit human- or agent-authored verdict before an accepted code line advances. It should intentionally replace upstream's branch-as-run identity, untracked TSV ledger, overwritten log, free-form stdout parsing, destructive discard reset, and agent-owned Git operations with Commander-owned lifecycle, structured measurements, durable artifacts, and retained Experiment commits.

The official repository is currently unchanged at commit [`228791f`](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117), pushed 2026-03-26. This finding pins every upstream source citation to that revision.

## What upstream actually promises

AutoResearch is deliberately a small repository and an instruction protocol for an externally launched coding agent. The human starts Claude, Codex, or another agent in the repository and points it at `program.md`; there is no model API, controller daemon, cloud provisioner, or application-owned runtime in the official workflow. [`README.md`, lines 42–50](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md#L42-L50)

Its operating contract is:

1. Create a fresh `autoresearch/<tag>` branch, inspect the small in-scope repository, verify prepared data, initialize `results.tsv`, and ask for confirmation before beginning. [`program.md`, lines 5–19](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L5-L19)
2. Run the unchanged program first to establish a local baseline. [`program.md`, lines 33–39](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L33-L39)
3. Modify only `train.py`; keep `prepare.py`, its evaluator, and the dependency set fixed. [`program.md`, lines 21–32](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L21-L32)
4. Commit the proposed change, run it, read `val_bpb` and peak VRAM from `run.log`, record the result, then either retain the commit or reset to the prior accepted state. [`program.md`, lines 90–106](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L90-L106)
5. Treat a run over ten minutes as a failure; repair trivial crashes and rerun, but record fundamentally broken ideas as crashes. [`program.md`, lines 108–110](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L108-L110)
6. Continue until the human interrupts. [`program.md`, lines 112–114](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L112-L114)

The fixed budget is 300 seconds of measured training time, excluding the first warm-up steps, startup/compilation, and final evaluation. The implementation accumulates synchronized step durations only after step 10 and evaluates after the budget is reached. [`prepare.py`, lines 27–32](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/prepare.py#L27-L32), [`train.py`, lines 538–604](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L538-L604), [`train.py`, lines 606–630](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L606-L630)

`val_bpb` is not a value printed by convention alone: the frozen evaluator computes total validation cross-entropy divided by the number of represented bytes and `log(2)`, excluding zero-byte special tokens. [`prepare.py`, lines 339–365](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/prepare.py#L339-L365) The official repository nonetheless presents `val_bpb` as this project's metric, not as a universal AutoResearch requirement. Battleground may therefore generalize the metric while retaining its essential declared properties: stable identity, direction, and a frozen implementation within a Research Run.

## Behavioral invariants V1 should preserve

### 1. A frozen comparison boundary

An Experiment is meaningful only relative to frozen inputs: preparation/data, evaluator, dependencies, mutable-file scope, execution profile, and budget. Upstream explicitly freezes `prepare.py`, the evaluator, and packages, while allowing broad changes inside `train.py`. [`README.md`, lines 9–17](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md#L9-L17), [`program.md`, lines 25–37](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L25-L37)

The reason is comparability, not devotion to those filenames. The README says the five-minute budget compares changes on one platform while explicitly warning that results are not comparable across different compute platforms. [`README.md`, lines 61–65](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md#L61-L65) Battleground should consequently treat an execution-profile change as a new comparison boundary rather than quietly mixing those measurements into one ranking.

### 2. Baseline first, then a sequential accepted line

The first evaluation establishes the baseline, and each subsequent Experiment starts from the current accepted state. A successful change advances that state; a rejected change must not influence the next candidate. This accepted-line ratchet is the core search behavior, independent of whether the implementation uses branches, worktrees, scratch copies, or another isolation mechanism. [`program.md`, baseline](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L39), [experiment loop](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L90-L106)

### 3. Measurement and verdict are distinct

Upstream's nominal rule is lower `val_bpb`, but its actual instructions also make VRAM a soft constraint and code simplicity part of the keep decision. Equal performance with simpler code can be kept; a tiny improvement with substantial ugly complexity can be rejected. [`program.md`, lines 33–37](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L33-L37) V1 must therefore record the Objective Metric as a measurement and the keep/discard decision plus reason as a separate verdict. Commander must not infer every verdict from numeric ordering alone.

### 4. Negative results are research output

Karpathy's published H100 run records 126 rows: 23 `keep`, 102 `discard`, and one `crash`, improving from `0.997900` to `0.969686`. Its discussion calls out both wins and dead ends and notes that warmup and a seed change did not reproduce across runs. [First-party session report](https://github.com/karpathy/autoresearch/discussions/43) The experiment history—not only the final code—is therefore part of the useful product.

### 5. Unattended continuation remains interruptible

The desired behavior is autonomous continuation until a human interrupts, but a Markdown sentence is not a reliable process-control primitive. Karpathy's March 2026 report says the Codex version he tested stopped despite the instruction and that he preferred an interactive session that remained visible and steerable. [First-party issue](https://github.com/karpathy/autoresearch/issues/57) This is historical evidence about one agent version, not a present limitation to encode. V1 should express continuation, interruption, steering, and restart as adapter capabilities and observable lifecycle events rather than assume every external agent obeys `NEVER STOP` identically.

## Upstream mechanics V1 should intentionally replace

### Branch-as-run and agent-owned Git

Upstream delegates branch creation, commits, resets, and repository inspection directly to the coding agent. Battleground's isolation and security goals require Commander to own those operations while preserving the accepted-line semantics. The agent should submit a candidate and verdict through Commander; it should not need repository metadata or credentials.

This is a replacement of mechanism, not behavior. Git remains the authoritative representation of code and lineage, while the Experiment Ledger becomes authoritative for Experiment history.

### Lossy records and destructive discard

The normal upstream ledger is an untracked five-column `results.tsv`, and each execution redirects into the same `run.log`. [`program.md`, lines 41–78](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L41-L78), [`program.md`, lines 96–105](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L96-L105), [`.gitignore`, lines 22–23](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/.gitignore#L22-L23)

The published TSV contains discarded hash `187e419`, but GitHub currently resolves the kept hash `bea057b` and returns “No commit found” for the discarded hash. [Published `results.tsv`](https://github.com/karpathy/autoresearch/blob/fedfef398bf89ad5c1581cecb1aa5108b71f8f5b/results.tsv#L1-L5), [kept commit API](https://api.github.com/repos/karpathy/autoresearch/commits/bea057b), [discarded commit API](https://api.github.com/repos/karpathy/autoresearch/commits/187e419) This is direct evidence that a short hash in the TSV does not preserve a rejected diff once the reset commit becomes unreachable.

V1 should instead retain each proposed change under a reachable Experiment-specific ref, preserve stdout/stderr and diagnostics as immutable artifacts, and append the complete outcome to the Experiment Ledger. A discard changes the accepted line; it does not erase the Experiment.

### Free-form output scraping and collapsed failures

Upstream asks the agent to grep two human-readable lines and treats empty output, timeout, OOM, code defects, and an intrinsically bad idea through a small `keep`/`discard`/`crash` vocabulary. [`program.md`, lines 41–62](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L41-L62), [`program.md`, lines 99–110](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L99-L110) Commander should ingest a versioned structured result while preserving raw process output. Execution state and termination cause should be recorded separately from the research verdict so a timeout, user interruption, invalid metric, failed correctness check, and process crash remain distinguishable.

### Hardware-local assumptions

The official implementation requires one NVIDIA GPU and directly selects CUDA, CUDA capability, BF16 autocast, and Flash Attention kernels. [`README.md`, requirements](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md#L21-L40), [platform support](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md#L67-L81), [`train.py`, kernel selection](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L20-L26), [device setup](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L457-L463) Provider agnosticism should therefore mean a stable provisioning/execution boundary plus a recorded execution profile—not an assertion that metrics produced on different hardware are directly comparable.

## Lessons from a credible extension

The maintained `pi-autoresearch` extension demonstrates that the loop can be generalized without embedding a model API. Its agent tools declare metric name, unit, and direction; execute with an explicit timeout; parse structured `METRIC name=value` lines; append results to JSONL; run separate correctness checks; display a live dashboard; and rehydrate context from session files after restart or compaction. [Extension overview](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/README.md#L28-L50), [session files and recovery](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/README.md#L90-L104), [runner source](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/extensions/pi-autoresearch/index.ts#L1678-L1693), [correctness checks](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/extensions/pi-autoresearch/index.ts#L1920-L1954)

Those capabilities validate Battleground's direction, but the extension's storage mechanics are not sufficient for V1:

- Full output spills to a temporary file, while the agent sees only a tail. [`index.ts`, output spill](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/extensions/pi-autoresearch/index.ts#L1754-L1829), [tail truncation](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/extensions/pi-autoresearch/index.ts#L1956-L1974)
- Only kept changes are committed; discard, crash, and checks-failed changes are checked out and cleaned away. [`index.ts`, lines 2375–2447](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/extensions/pi-autoresearch/index.ts#L2375-L2447)
- The in-memory result is mutated, Git may be changed, and JSONL is then appended in separate fallible steps; a JSONL write failure is only appended to tool text. [`index.ts`, state mutation](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/extensions/pi-autoresearch/index.ts#L2276-L2309), [Git and JSONL writes](https://github.com/davebcn87/pi-autoresearch/blob/00062fb9cc425e71d82e75445dc5b6ad31c32f0e/extensions/pi-autoresearch/index.ts#L2375-L2435)

The decision-relevant lesson is to adopt its **explicit control surfaces, structured measurements, correctness gates, and recovery model**, while designing Battleground's Experiment Ledger, artifact retention, and Git transitions as one recoverable Commander-owned workflow.

## Corrections to the prior local audit

The earlier note is directionally sound, but this validation found three details that later specification work must not repeat:

1. Its historical `spawn.sh` commit links contain incorrect full hashes. The correct initial commit is [`b11d6f2`](https://github.com/karpathy/autoresearch/blob/b11d6f283f866eb7e10fb776a4b8553fef873fd5/spawn.sh), and the correct removal commit is [`1e207aa`](https://github.com/karpathy/autoresearch/commit/1e207aaf2131df2a4efde060e7c38f5d98935bc3). The substantive observation remains valid: the initial script created per-GPU branches/worktrees, launched interactive Claude or Codex sessions in `tmux`, and nudged idle panes, but was removed from the minimal repository. [`spawn.sh`, workers](https://github.com/karpathy/autoresearch/blob/b11d6f283f866eb7e10fb776a4b8553fef873fd5/spawn.sh#L38-L81), [idle nudging](https://github.com/karpathy/autoresearch/blob/b11d6f283f866eb7e10fb776a4b8553fef873fd5/spawn.sh#L149-L189)
2. The published results file has **126** Experiment rows—23 kept, 102 discarded, one crash—even though its publication commit message says “125 experiments.” [Published file](https://github.com/karpathy/autoresearch/blob/fedfef398bf89ad5c1581cecb1aa5108b71f8f5b/results.tsv), [publication commit](https://github.com/karpathy/autoresearch/commit/fedfef398bf89ad5c1581cecb1aa5108b71f8f5b)
3. The cited nanochat transfer commit does **not** support a conclusion that AutoResearch gains failed to transfer. It explicitly says the d12 tuning “generalized easily to larger models,” and the following leaderboard commit reports a time-to-GPT-2 improvement from 2.02 to 1.80 hours. [`nanochat` transfer commit](https://github.com/karpathy/nanochat/commit/6ed7d1d82cee16c2e26f45d559ad3338447a6c1b), [leaderboard follow-up](https://github.com/karpathy/nanochat/commit/f0686049) Confirmation still matters—the first-party session report itself documents individual findings that failed to reproduce—but the transfer commit is positive evidence, not negative evidence.

## Required V1 specification consequences

Later Wayfinder tickets should treat the following as constraints to resolve into precise schemas and state transitions:

- A Research Run freezes its preparation/evaluation contract, dependency definition, editable-file allowlist, Objective Metric definition, execution profile, and budget.
- A baseline is required before candidate Experiments can advance the accepted line.
- Each Experiment records its base revision, hypothesis, submitted change, execution identity, timestamps, termination cause, raw artifacts, structured primary and secondary measurements, verdict, verdict reason, and deciding actor.
- Measurement, execution outcome, verdict, and advancement of the accepted line are distinct concepts; the lifecycle must not compress them into one status.
- Every submitted Experiment remains inspectable after keep, discard, crash, timeout, invalid result, or interruption.
- Commander owns candidate application, execution, retained Git refs, and accepted-line transitions. An external agent operates through the protocol rather than through Git.
- Results may be ranked together only inside the same frozen comparison boundary. Cross-profile results remain visible but are not silently treated as equivalent.
- Unattended continuation, live steering, restart, and transcript visibility are capability claims of an agent adapter, not invariants of a Markdown prompt.
- Provider provisioning is separate from experiment execution: a local or SSH-accessible target can satisfy the common runner contract while provider adapters obtain and release targets.

This preserves what makes Karpathy AutoResearch scientifically useful while giving Battleground the durable, inspectable, provider-agnostic behavior its V1 destination requires.
