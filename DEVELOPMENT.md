# Development

## Setup and validation

Install Python 3.12 or newer and the nils-cli version recorded in
[manifest.json](manifest.json). The development gate needs `agent-docs` and `devlog`
from that release, Docker with BuildKit, Make, and Podman on Linux with cgroup
v2. Runtime acceptance uses rootful Podman; the invoking role needs permission
to run it (for example through sudo).

Before editing, run:

```sh
agent-docs --docs-home "$PWD" preflight --intent project-dev
```

Before PR delivery, run:

```sh
.agents/scripts/pre-pr.sh
```

This checks manifest syntax, development-log structure, and the strict project
docs audit. The maintainer workflow invokes the pre-PR script through
`agent-run exec`. CI runs the same script on GitHub-hosted Ubuntu runners after
installing the checksum-pinned official nils-cli archive.

## Source ownership

`manifest.json` owns exact component versions, official artifact URLs, checksums,
and the Ubuntu Linux x64 base digest. Source kits use exact commit SHAs.
Workbench's nested `source` object owns the installer source pin; update it,
the release-manifest checksum, and the paired DSH kit pin together with a new
Workbench release. Workbench 0.2.2 retains nils-cli 1.31.1 internally for its
hook contract; the general toolchain nils-cli pin is independently 1.31.14.

## M1 build and runtime acceptance

```sh
make build
sudo make acceptance
```

The image uses the manifest's immutable Ubuntu snapshot and checksum-pinned
artifacts. Source archives must match the pinned upstream Git objects. Both
agent harnesses and the general nils-cli are installed during the build.
Workbench's authenticated release, installer checkout, package manager, and
owner input are prepared, but its official installation runs at acceptance.
The empty owner configuration contains no provider credentials.

Acceptance imports the local Docker image into Podman and boots `/sbin/init`
as PID 1 with `--systemd=always --cgroupns=private` on cgroup v2. Podman delegates
a writable container cgroup subtree; there are no elevated capability flags,
privileged mode, host systemd sockets, or host cgroup bind mounts. See
[Podman's systemd mode](https://docs.podman.io/en/stable/markdown/podman-run.1.html#systemd-true-false-always).
The container starts its own root user manager directly, with a service drop-in
setting `PAMName=` and `XDG_RUNTIME_DIR=/run/user/0`. This avoids a host PAM login
and the inherited audit-login-ID limitation without adding audit capabilities;
the real systemd user manager and its delegated cgroups remain mandatory.
It then invokes the unchanged
Workbench 0.2.2 owner installer with its plan digest. Acceptance requires the
installer receipt to report an available finish-line probe and healthy runtime
kit. This validates installation and containment, not live-provider behavior.

After installation, acceptance disconnects the container network, runs
`make versions`, and proves that a deliberately wrong Node pin fails while the
other components are still reported. The version gate inspects tool output,
source revisions, the Workbench receipt, and its authenticated runtime-kit
archive. It never downloads anything. To inspect an independently booted and
installed sandbox, use `sudo make versions CONTAINER=<container-id>`.
The acceptance container is stopped and removed on exit; the prepared image
remains available for later runs and a private overlay layer.

The local acceptance and public GitHub-hosted Ubuntu
[CI run 37080220973](https://github.com/sympoies/agent-sandbox/actions/runs/37080220973) both pass: the official
installer reports `finishLineHostProbe=available` and `runtimeKitDoctor=healthy`,
all eleven component pins agree offline, and the deliberate wrong pin is
rejected. Five unit regressions and repository conventions also pass. This
selects runtime systemd acceptance without an upstream container-mode change.
Workbench source and its frozen graph remain unchanged. Image publication and
host activation require separate authorization.

## M2 offline scenarios

`make acceptance` now also runs every public scenario after installation and
network disconnection. The `sandbox-acceptance` hosted CI job preserves its
machine-readable result as the `scenario-results` artifact. Local acceptance
writes `.cache/scenario-results.json`; set `SCENARIO_RESULT` to choose another
output file. A failing contract makes acceptance fail.

For an independently booted, installed sandbox whose network is disconnected:

```sh
sudo make scenario CONTAINER=<container-id> SCENARIO=devlog-fragments
sudo make scenario CONTAINER=<container-id>  # all public scenarios
```

The target emits one `agent-sandbox.scenarios.v1` JSON object on stdout; script
diagnostics go to stderr. It requires systemd as PID 1 and only the loopback
interface. Every scenario runs with a disposable working directory, isolated
HOME and Git configuration, and a 120-second timeout. Its directory owns
`run.sh` and `expected.json`; see the [scenario contract](tests/integration/README.md).
`SCENARIO_ROOT=<container-side-directory>` adds a second set of scenarios that
has already been staged in a container. Duplicate names fail. This is the
extension hook for M2b; no private overlay or private scenario is implemented.

The [devlog fragment scenario](tests/integration/devlog-fragments/expected.json)
uses released nils-cli 1.31.14 with `DEVLOG_LAYOUT=fragments` and a local bare Git
remote. It verifies both branch merge orders with `devlog check` after every
merge, unchanged shared files during entry creation, a no-op fold without a
commit, exact month entries and consumed fragments, retention of today's and
future fragments, deterministic and idempotent folding, and a real rejected
push followed by fetch, reset of the disposable clone, rerun and successful
push preserving the concurrent entry. Commit creation and retry belong to this
scenario's simulated fold job; `devlog fold` itself only changes files.

The negative month-edit probe records the tool's actual contract: a
structurally valid correction to a folded month file is accepted by
`devlog check --base origin/main`. Editing a merged pending fragment is rejected
as `fragment-modified`. Month-file policy enforcement in PRs belongs to
[agent-runtime-kit #218](https://github.com/sympoies/agent-runtime-kit/issues/218);
this sandbox does not claim that nils-cli rejects every month-file edit.
See the [released tool documentation](https://github.com/sympoies/nils-cli/blob/v1.31.14/crates/devlog/README.md).

Provider branch protection, App identity and verified or required signed
commits cannot be tested against an offline bare remote. They remain out of
scope here and must pass in #218's real provider test repository before
rollout. Scenario fixture commits use an explicitly synthetic identity and
are unsigned. No runtime-kit policy or CI fold rollout is included in M2.

If a scenario exposes a nils-cli defect, reproduce it without a workaround,
file an English upstream issue, and map that check to the issue URL in
`expected_failures`. Expected failures remain visible in JSON; an unexpected
pass fails so the exemption must be reviewed and removed after a fix. Crashes,
missing checks and malformed output always fail. Report the issue to the
maintainer through the private coordination mailbox.

Keep future deterministic scenarios under
[tests/integration](tests/integration/README.md). M3 will add candidate selection;
component artifact pins and source revisions are independent fields so those
later scenarios can select nils-cli and agent-runtime-kit candidates together.

### Candidate kit devlog wiring

To verify a kit change without downloading or installing a candidate, stage its
checkout in the pinned container and select it explicitly:

```sh
sudo podman cp /path/to/reviewed-kit "$CONTAINER:/opt/kit-candidate"
sudo make scenario CONTAINER="$CONTAINER" SCENARIO=devlog-fragments \
  KIT_CANDIDATE=/opt/kit-candidate
```

The runner passes only this explicit path through its isolated environment;
`--kit-candidate` never fetches, installs, or activates runtime surfaces. The
devlog scenario derives `DEVLOG_LAYOUT` from the candidate kit's shared render,
checks the unset/off renders, and invokes its fragment-aware check owner. It
uses `expected-candidate.json`, keeping the existing pinned scenario unchanged
when no candidate is selected. A missing owner fails before scenario execution.
The candidate contract records month-file rejection as an expected failure for
[nils-cli #2082](https://github.com/sympoies/nils-cli/issues/2082); all other checks
must pass. This remains a visible production enablement blocker, not a workaround.
After that tool fix, an unexpected pass forces removal of the exemption.
Provider protection, App signatures, and the real fold workflow remain separate.

## History and delivery

Record completed changes with `devlog new`, refresh the month index with
`devlog index`, and run `devlog check`. Root README is user-facing; contributor
requirements live here; durable history lives under `docs/`.

Keep all public artifacts generic and free of private deployment identities,
paths, accounts, credentials, or topology. Use signed semantic commits in
managed feature worktrees and the normal reviewed PR workflow. Merge only after
CI is green. Image pushes, release tags, releases, and deployment require
separate explicit authorization; the scaffold has no publication workflow.
