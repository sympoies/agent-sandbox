#!/usr/bin/env bash
set -euo pipefail
container=${1:?Set CONTAINER to a booted offline sandbox.}
podman=${2:-podman}
scenario=${3:-all}
extra_root=${4:-}
args=(--require-sandbox --root /opt/sandbox/tests/integration --scenario "$scenario")
# M2b can stage additional scenario directories inside its own overlay image.
if [[ -n $extra_root ]]; then
  args+=(--root "$extra_root")
fi
exec "$podman" exec "$container" python3 /opt/sandbox/scripts/scenarios.py "${args[@]}"
