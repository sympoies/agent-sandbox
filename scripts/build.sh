#!/usr/bin/env bash
set -euo pipefail
manifest=${1:-manifest.json}
image=${2:-agent-sandbox:local}
docker=${3:-docker}
mkdir -p .cache
context=$(mktemp -d .cache/build.XXXXXX)
trap 'rm -rf "$context"' EXIT
cp Dockerfile Makefile .dockerignore "$context/"
cp "$manifest" "$context/manifest.json"
cp -R scripts tests "$context/"
base=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["base_image"])' "$manifest")
snapshot=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["ubuntu_snapshot"])' "$manifest")
ca_url=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["build_tools"]["ca-certificates"]["url"])' "$manifest")
ca_sha=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["build_tools"]["ca-certificates"]["sha256"])' "$manifest")
"$docker" build --platform linux/amd64 --build-arg BASE_IMAGE="$base" \
  --build-arg UBUNTU_SNAPSHOT="$snapshot" --build-arg CA_URL="$ca_url" --build-arg CA_SHA256="$ca_sha" --tag "$image" "$context"
