#!/usr/bin/env bash
set -euo pipefail

isort app tests
black app tests
