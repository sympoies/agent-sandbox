#!/usr/bin/env bash
set -euo pipefail
candidate=$(mktemp)
output=$(mktemp)
trap 'rm -f "$candidate" "$output"' EXIT
python3 - "$candidate" <<'PY'
import json,sys
from pathlib import Path
manifest = json.loads(Path('manifest.json').read_text())
manifest['components']['node']['version'] = '0.0.0'
Path(sys.argv[1]).write_text(json.dumps(manifest))
PY
if make --no-print-directory versions MANIFEST="$candidate" >"$output" 2>&1; then
  cat "$output"
  echo 'ERROR: deliberately wrong Node pin passed' >&2
  exit 1
fi
cat "$output"
grep -E '^node: .+ \(expected 0\.0\.0\)' "$output"
echo 'Wrong-pin rejection verified.'
