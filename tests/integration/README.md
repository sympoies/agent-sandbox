# Integration scenarios

Each public scenario is a directory containing `run.sh` and `expected.json`.
The script runs with Bash in a disposable working directory, with an isolated
HOME and Git configuration. It must emit exactly one JSON object with a
`checks` object on stdout. It may add `observations`; diagnostics go to stderr.
Use paths relative to the script to read fixtures. Scripts run offline in the
pinned sandbox, and must not fetch tools, call providers or use credentials.

A contract declares the exact check keys and expected JSON values:

```json
{
  "schema_version": 1,
  "checks": {"example_behavior": true},
  "expected_failures": {}
}
```

A missing, extra or mismatched check fails. Script failure, invalid output,
invalid contracts and timeouts fail. For a confirmed tool defect, keep the
correct expected value and add its check key and public upstream issue URL to
`expected_failures`. A mismatching value then reports `expected-fail`; a match
reports `unexpected-pass` and fails pending review of the exemption. A crash or
missing check cannot be waived this way. There are no expected failures in the
initial devlog scenario.

Run one scenario or all with `make scenario CONTAINER=<container-id>
SCENARIO=devlog-fragments` or omit `SCENARIO`. The target requires a booted
systemd sandbox with only its loopback interface and emits
`agent-sandbox.scenarios.v1` JSON. `make acceptance` runs them automatically and
saves `.cache/scenario-results.json`. Exit zero means all contracts passed or
only documented expected failures remain; inspect `status` to distinguish them.

For runner development, `python3 scripts/scenarios.py --root tests/integration`
executes contracts directly without the sandbox prerequisite. This is a local
smoke check, not offline container acceptance. Unit regressions use disposable
scripts to test the runner's fail-closed boundary.

The devlog scenario covers isolated branch entries and both merge orders,
no-op, normal and idempotent folds, identical fold bytes in independent clones,
retained current/future entries, a stale push and retry, month corrections, and
merged-fragment immutability. The [contract](devlog-fragments/expected.json)
contains the individual assertions. See [DEVELOPMENT.md](../../DEVELOPMENT.md)
for provider-level exclusions and the #218 rollout boundary.

M2b may supply additional scenario directories already staged inside a private
container by setting `SCENARIO_ROOT` to their container-side parent directory.
The runner adds that root to the public one and rejects duplicate scenario
names. No private overlay is implemented here. M3 will add candidate selection;
component artifact pins and agent-runtime-kit source revisions remain
independent fields. M4 adds a local-model smoke run.
