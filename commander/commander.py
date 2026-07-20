"""PROTOTYPE: a frozen Commander stdio protocol fixture, not application code."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any


PROTOCOL = "battleground.commander/1"


class Protocol:
    def __init__(self) -> None:
        self.sequence = 0

    def emit(self, kind: str, **fields: Any) -> None:
        frame = {
            "protocol": PROTOCOL,
            "kind": kind,
            "seq": self.sequence,
            **fields,
        }
        self.sequence += 1
        print(json.dumps(frame, separators=(",", ":")), flush=True)

    def respond(self, request_id: str | None, ok: bool, **fields: Any) -> None:
        self.emit("response", id=request_id, ok=ok, **fields)


def serve_stdio() -> int:
    protocol = Protocol()
    protocol.emit("hello", version=1, pid=os.getpid())

    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
        except json.JSONDecodeError as error:
            protocol.respond(None, False, error=f"invalid JSON: {error.msg}")
            continue

        request_id = request.get("id")
        if request.get("protocol") != PROTOCOL:
            protocol.respond(request_id, False, error="unsupported protocol")
            continue

        operation = request.get("op")
        if operation == "ping":
            protocol.respond(request_id, True, result={"pong": True})
        elif operation == "stream":
            count = int(request.get("payload", {}).get("count", 5))
            protocol.respond(request_id, True, result={"accepted": count})
            for index in range(count):
                protocol.emit(
                    "event",
                    event="prototype.telemetry",
                    data={"index": index + 1, "total": count},
                )
                time.sleep(0.08)
        elif operation == "shutdown":
            protocol.respond(request_id, True, result={"shutdown": "graceful"})
            return 0
        elif operation == "crash":
            print("PROTOTYPE: simulated Commander crash", file=sys.stderr, flush=True)
            os._exit(42)
        else:
            protocol.respond(request_id, False, error=f"unknown operation: {operation}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="battleground-commander")
    subcommands = parser.add_subparsers(dest="command", required=True)
    serve = subcommands.add_parser("serve")
    serve.add_argument("--stdio", action="store_true", required=True)
    arguments = parser.parse_args()
    if arguments.command == "serve":
        return serve_stdio()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
