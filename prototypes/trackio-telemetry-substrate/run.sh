#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../.."
exec uv run --with 'trackio==0.31.5' python prototypes/trackio-telemetry-substrate/prototype.py

