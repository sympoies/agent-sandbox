# Development

## Setup and validation

Install Python 3.12 or newer and the nils-cli version recorded in
[manifest.json](manifest.json). The scaffold needs `agent-docs` and `devlog`
from that release; Docker and Make will be needed for M1.

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
hook contract; the general toolchain nils-cli pin is independently 1.31.13.

M1 has not completed: the official Workbench owner installer requires an active
systemd user manager unavailable in ordinary Docker build containers. Resolve
that installation boundary before enabling image build and version gates in CI.
Do not bypass the owner installer's host-acceptance checks.

Keep future deterministic scenarios under
[tests/integration](tests/integration/README.md). M3 will add candidate selection;
component artifact pins and source revisions are independent fields so those
later scenarios can select nils-cli and agent-runtime-kit candidates together.

## History and delivery

Record completed changes with `devlog new`, refresh the month index with
`devlog index`, and run `devlog check`. Root README is user-facing; contributor
requirements live here; durable history lives under `docs/`.

Keep all public artifacts generic and free of private deployment identities,
paths, accounts, credentials, or topology. Use signed semantic commits in
managed feature worktrees and the normal reviewed PR workflow. Merge only after
CI is green. Image pushes, release tags, releases, and deployment require
separate explicit authorization; the scaffold has no publication workflow.
