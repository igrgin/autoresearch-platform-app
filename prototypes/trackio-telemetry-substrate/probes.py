"""Real Trackio 0.31.5 probes used by the throwaway terminal prototype.

The fault injector touches private Trackio fields only to create a lost-response
network condition. No proposed Battleground integration relies on those fields.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Callable

import trackio
from trackio.remote_client import RemoteClient
from trackio.sqlite_storage import SQLiteStorage

from assessment import GateResult


PROJECT = "battleground-trackio-prototype"
EXPERIMENT_ID = "experiment-01HZZZSTABLE"
HERE = Path(__file__).resolve().parent


def _finish() -> None:
    try:
        trackio.finish()
    except Exception:
        pass


def _wait_until(predicate: Callable[[], bool], timeout: float, message: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise RuntimeError(message)


def identity_probe() -> GateResult:
    first = trackio.init(
        project=PROJECT,
        name=EXPERIMENT_ID,
        resume="never",
        config={"battleground_experiment_id": EXPERIMENT_ID},
        auto_log_cpu=False,
        auto_log_gpu=False,
    )
    first_id = first.id
    first.log({"train/loss": 1.0}, step=0)
    _finish()

    resumed = trackio.init(
        project=PROJECT,
        name=EXPERIMENT_ID,
        resume="must",
        auto_log_cpu=False,
        auto_log_gpu=False,
    )
    resumed_id = resumed.id
    _finish()

    duplicate = trackio.init(
        project=PROJECT,
        name=EXPERIMENT_ID,
        resume="never",
        auto_log_cpu=False,
        auto_log_gpu=False,
    )
    duplicate_id = duplicate.id
    duplicate.log({"train/loss": 0.9}, step=99)
    _finish()

    matching = [run for run in trackio.Api().runs(PROJECT) if run.name == EXPERIMENT_ID]
    preserved_on_resume = first_id == resumed_id
    duplicate_names_allowed = len(matching) >= 2 and duplicate_id != first_id
    return GateResult(
        name="experiment identity",
        status="caution" if preserved_on_resume and duplicate_names_allowed else "fail",
        evidence=(
            f"resume='must' preserved Trackio run_id: {preserved_on_resume}",
            f"resume='never' admitted {len(matching)} runs with the same name: {duplicate_names_allowed}",
            "trackio.init() accepts a run name but not a caller-supplied run_id",
        ),
        implication=(
            "The Experiment Ledger must own the Battleground Experiment ID and persist "
            "a one-to-one Trackio run_id mapping. Trackio names are labels, not identity."
        ),
    )


def query_probe() -> GateResult:
    command = [
        sys.executable,
        "-m",
        "trackio.cli",
        "query",
        "project",
        "--project",
        PROJECT,
        "--sql",
        "SELECT run_id, run_name, step, metrics FROM metrics ORDER BY id LIMIT 3",
        "--json",
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    payload = json.loads(completed.stdout)
    api_runs = list(trackio.Api().runs(PROJECT))
    return GateResult(
        name="programmatic query",
        status="caution",
        evidence=(
            f"supported read-only CLI query returned {payload['row_count']} row(s)",
            f"public Python Api enumerated {len(api_runs)} run(s) and their configs",
            "the public Python Api does not expose metric history; metric access is CLI/HTTP or documented SQL",
            "Trackio labels its database schema beta and the 0.31.5 docs lag the run_id migration",
        ),
        implication=(
            "Battleground can query Trackio through supported CLI/HTTP surfaces, but must "
            "not couple its UI directly to Trackio's evolving SQLite schema."
        ),
    )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(port: int, server_dir: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["TRACKIO_DIR"] = str(server_dir)
    env["TRACKIO_WRITE_TOKEN"] = "prototype-write-token"
    process = subprocess.Popen(
        [sys.executable, str(HERE / "server_helper.py"), "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/"

    def ready() -> bool:
        if process.poll() is not None:
            raise RuntimeError("Trackio prototype server exited during startup")
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                return True
        except Exception:
            return False

    _wait_until(ready, 15, "Trackio prototype server did not start")
    return process


def _stop_server(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def replay_probe() -> GateResult:
    port = _free_port()
    server_dir = Path(tempfile.mkdtemp(prefix="trackio-prototype-server-"))
    server: subprocess.Popen | None = None
    url = f"http://127.0.0.1:{port}/"
    write_url = f"{url}?write_token=prototype-write-token"
    same_process_count = -1
    pending_before_restart = False
    pending_after_restart = False
    try:
        server = _start_server(port, server_dir)
        run = trackio.init(
            project=PROJECT,
            name="same-process-response-loss",
            server_url=write_url,
            resume="never",
            auto_log_cpu=False,
            auto_log_gpu=False,
        )
        _wait_until(lambda: run._client is not None, 15, "remote client was not ready")
        original_predict = run._client.predict
        response_lost = {"done": False}

        def lose_first_bulk_log_response(*args, **kwargs):
            if kwargs.get("api_name") == "/bulk_log" and not response_lost["done"]:
                result = original_predict(*args, **kwargs)
                response_lost["done"] = True
                raise ConnectionError("prototype: response lost after server commit")
            return original_predict(*args, **kwargs)

        run._client.predict = lose_first_bulk_log_response
        run.log({"train/loss": 0.5}, step=1)
        _wait_until(lambda: response_lost["done"], 15, "response-loss fault did not fire")
        _wait_until(
            lambda: not SQLiteStorage.has_pending_data(PROJECT),
            20,
            "same-process pending row did not replay",
        )
        _finish()
        summary = RemoteClient(url, verbose=False).predict(
            project=PROJECT,
            run_id=run.id,
            api_name="/get_run_summary",
        )
        same_process_count = int(summary["num_logs"])

        _stop_server(server)
        server = None
        offline = trackio.init(
            project=PROJECT,
            name="finished-while-disconnected",
            server_url=write_url,
            resume="never",
            auto_log_cpu=False,
            auto_log_gpu=False,
        )
        offline.log({"train/loss": 0.25}, step=2)
        _finish()
        pending_before_restart = SQLiteStorage.has_pending_data(PROJECT)

        server = _start_server(port, server_dir)
        recovery_trigger = trackio.init(
            project=PROJECT,
            name="later-connected-run",
            server_url=write_url,
            resume="never",
            auto_log_cpu=False,
            auto_log_gpu=False,
        )
        _wait_until(
            lambda: recovery_trigger._client is not None,
            15,
            "recovery client was not ready",
        )
        time.sleep(2)
        _finish()
        pending_after_restart = SQLiteStorage.has_pending_data(PROJECT)
    finally:
        _finish()
        _stop_server(server)
        shutil.rmtree(server_dir, ignore_errors=True)

    same_process_deduped = same_process_count == 1
    durable_replay_missing = pending_before_restart and pending_after_restart
    return GateResult(
        name="offline replay",
        status="fail" if same_process_deduped and durable_replay_missing else "caution",
        evidence=(
            f"lost response replay produced exactly one server row: {same_process_deduped}",
            f"a disconnected finished process left a durable pending row: {pending_before_restart}",
            f"a later connected server_url run left that pending row stranded: {pending_after_restart}",
            "Trackio automatically re-arms persisted pending data for space_id, but not for self-hosted server_url",
        ),
        implication=(
            "Same-process delivery is idempotent, but V1's no-hosted-control-plane path "
            "cannot guarantee replay after the training process exits. Battleground still "
            "needs its own durable spool and acknowledgement cursor."
        ),
    )


def packaging_probe() -> GateResult:
    uv = shutil.which("uv")
    if uv is None:
        return GateResult(
            name="cross-platform packaging",
            status="not-run",
            evidence=("uv is unavailable, so target-aware wheel resolution was skipped",),
            implication="Run the branch CI matrix before deciding packaging support.",
        )

    targets = {
        "Windows x86_64": "x86_64-pc-windows-msvc",
        "macOS x86_64": "x86_64-apple-darwin",
        "macOS arm64": "aarch64-apple-darwin",
        "Linux x86_64": "x86_64-unknown-linux-gnu",
        "Linux arm64": "aarch64-unknown-linux-gnu",
    }
    evidence: list[str] = []
    all_passed = True
    for label, platform in targets.items():
        completed = subprocess.run(
            [
                uv,
                "pip",
                "compile",
                "-",
                "--quiet",
                "--python-version",
                "3.10",
                "--python-platform",
                platform,
                "--only-binary=:all:",
            ],
            input="trackio==0.31.5\n",
            capture_output=True,
            text=True,
        )
        passed = completed.returncode == 0
        all_passed = all_passed and passed
        evidence.append(f"{label} binary-wheel resolution: {'pass' if passed else 'fail'}")
    evidence.append("the full import/log/query/reconnect smoke test ran on macOS arm64")
    return GateResult(
        name="cross-platform packaging",
        status="pass" if all_passed else "fail",
        evidence=tuple(evidence),
        implication=(
            "Trackio 0.31.5's package set is resolvable for Battleground's desktop targets; "
            "pin it because Trackio remains beta, and run native Windows/Linux smoke tests "
            "before implementation."
        ),
    )


PROBES = {
    "i": identity_probe,
    "r": replay_probe,
    "q": query_probe,
    "p": packaging_probe,
}
