#!/usr/bin/env sh
set -e

ROOT_DIR=$(cd "$(dirname "$0")/../../.." && pwd)
exec "$ROOT_DIR/infra/hooks/predeploy.sh"
