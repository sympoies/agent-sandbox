#!/usr/bin/env bash
set -euo pipefail
python3 -m json.tool manifest.json >/dev/null
make test
devlog check
agent-docs --docs-home "$PWD" --project-path "$PWD" audit --target project --strict
