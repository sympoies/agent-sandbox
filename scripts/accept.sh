#!/usr/bin/env bash
set -euo pipefail
image=${1:-agent-sandbox:local}
docker=${2:-docker}
podman=${3:-podman}
scenario_result=${4:-.cache/scenario-results.json}
# Podman owns a writable delegated cgroup subtree in its private namespace.
# No host cgroup bind, systemd socket, elevated capabilities, or privileged mode.
[[ $("$podman" info --format '{{.Host.CgroupsVersion}}') == v2 ]] || {
  echo 'Acceptance requires cgroup v2.' >&2
  exit 1
}
"$docker" save "$image" | "$podman" load
container=$("$podman" run --detach --pull=never --systemd=always --cgroupns=private \
  --network podman "$image" /sbin/init)
cleanup() {
  "$podman" logs "$container" || true
  "$podman" stop --time 10 "$container" >/dev/null || true
  "$podman" rm "$container" >/dev/null || true
}
trap cleanup EXIT
ready=false
for ((attempt=0; attempt<60; attempt++)); do
  if "$podman" exec "$container" systemctl start user@0.service && \
    "$podman" exec --env XDG_RUNTIME_DIR=/run/user/0 \
      --env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus \
      "$container" systemctl --user show-environment; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  "$podman" exec "$container" systemctl status user@0.service --no-pager || true
  "$podman" exec "$container" journalctl -u user@0.service --no-pager -n 30 || true
  echo 'Systemd user manager did not become ready.' >&2
  exit 1
fi
"$podman" exec "$container" sh -c 'test "$(cat /proc/1/comm)" = systemd && test "$(stat -fc %T /sys/fs/cgroup)" = cgroup2fs'
"$podman" exec --env XDG_RUNTIME_DIR=/run/user/0 \
  --env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus \
  "$container" python3 /opt/sandbox/scripts/install.py finish
"$podman" exec "$container" python3 -c \
  'import json; r=json.load(open("/opt/workbench/installed-unit-receipt.json")); assert r["finishLineHostProbe"] == "available"; assert r["runtimeKitDoctor"] == "healthy"; print("Official installer: finish-line available; runtime-kit healthy.")'
# Version probes and the deliberate mismatch must work with networking removed.
"$podman" network disconnect podman "$container"
make --no-print-directory versions CONTAINER="$container" PODMAN="$podman"
make --no-print-directory test-wrong-pin CONTAINER="$container" PODMAN="$podman"
mkdir -p "$(dirname "$scenario_result")"
if make --silent scenario CONTAINER="$container" PODMAN="$podman" > "$scenario_result"; then
  cat "$scenario_result"
else
  cat "$scenario_result"
  exit 1
fi
echo 'Sandbox runtime and scenario acceptance passed.'
