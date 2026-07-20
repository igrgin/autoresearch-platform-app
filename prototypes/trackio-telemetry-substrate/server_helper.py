"""Run an isolated Trackio server for the reconnect probe."""

from __future__ import annotations

import argparse

import trackio


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    trackio.show(
        open_browser=False,
        block_thread=True,
        host="127.0.0.1",
        server_port=args.port,
    )


if __name__ == "__main__":
    main()

