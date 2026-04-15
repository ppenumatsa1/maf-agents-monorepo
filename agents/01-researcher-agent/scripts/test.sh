#!/usr/bin/env bash
set -euo pipefail

# Local test suite runs with auth disabled to isolate app and workflow behavior.
export REQUIRE_AUTH=false

pytest --ignore=tests/test_smoke_live.py
