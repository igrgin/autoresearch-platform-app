"""PROTOTYPE — throwaway Trackio telemetry-substrate decision probe.

Question: can a bounded Trackio 0.31.5 integration preserve Battleground's
stable Experiment identity, offline idempotent replay, supported programmatic
query access, and cross-platform packaging without becoming a lifecycle
authority? The prototype exercises those boundaries and renders the full
assessment after every action.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from dataclasses import asdict
from pathlib import Path


SCRATCH = tempfile.TemporaryDirectory(prefix="battleground-trackio-prototype-")
os.environ["TRACKIO_DIR"] = str(Path(SCRATCH.name) / "client")

from assessment import AssessmentState, GateResult, record  # noqa: E402
from probes import PROBES  # noqa: E402


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
STATUS = {"pass": "PASS", "caution": "CAUTION", "fail": "FAIL", "not-run": "NOT RUN"}


def render(state: AssessmentState, last_action: str = "ready") -> None:
    print("\033[2J\033[H", end="")
    print(f"{BOLD}Trackio as a Battleground telemetry substrate{RESET}")
    print(f"{DIM}Trackio 0.31.5 · scratch data {SCRATCH.name}{RESET}")
    print(f"{DIM}Last action: {last_action}{RESET}\n")
    for name in (
        "experiment identity",
        "offline replay",
        "programmatic query",
        "cross-platform packaging",
    ):
        result = state.results.get(name)
        if result is None:
            print(f"{BOLD}{name}{RESET}: NOT RUN")
            continue
        print(f"{BOLD}{name}{RESET}: {STATUS[result.status]}")
        for item in result.evidence:
            print(f"  - {item}")
        print(f"  {DIM}{result.implication}{RESET}")
    print(f"\n{BOLD}Candidate verdict{RESET}\n{state.verdict}")
    print(
        f"\n{BOLD}[i]{RESET} identity  {BOLD}[r]{RESET} replay  "
        f"{BOLD}[q]{RESET} query  {BOLD}[p]{RESET} packaging  "
        f"{BOLD}[a]{RESET} all  {BOLD}[x]{RESET} exit"
    )


def run_probe(state: AssessmentState, key: str) -> tuple[AssessmentState, str]:
    probe = PROBES[key]
    try:
        result = probe()
    except Exception as error:
        result = GateResult(
            name={"i": "experiment identity", "r": "offline replay", "q": "programmatic query", "p": "cross-platform packaging"}[key],
            status="fail",
            evidence=(f"probe error: {error}", traceback.format_exc(limit=2).strip()),
            implication="The prototype could not establish this gate.",
        )
    return record(state, result), f"ran {result.name}"


def run_all(state: AssessmentState, *, display: bool = True) -> AssessmentState:
    for key in ("i", "r", "q", "p"):
        state, action = run_probe(state, key)
        if display:
            render(state, action)
    return state


def batch() -> int:
    state = run_all(AssessmentState(), display=False)
    payload = {
        "results": {name: asdict(result) for name, result in state.results.items()},
        "verdict": state.verdict,
    }
    print(json.dumps(payload, indent=2))
    return 0


def interactive() -> int:
    state = AssessmentState()
    action = "ready"
    while True:
        render(state, action)
        choice = input("> ").strip().lower()[:1]
        if choice == "x":
            return 0
        if choice == "a":
            state = run_all(state)
            action = "ran all probes"
        elif choice in PROBES:
            state, action = run_probe(state, choice)
        else:
            action = f"unknown key: {choice!r}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true")
    args = parser.parse_args()
    return batch() if args.batch else interactive()


if __name__ == "__main__":
    sys.exit(main())
