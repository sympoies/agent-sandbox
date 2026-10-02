#!/usr/bin/env bash
set -euo pipefail
python3 -m json.tool manifest.json >/dev/null
devlog check
agent-docs audit --target project --strict
