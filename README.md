# agent-sandbox

A Linux container project that pins an exact agent toolchain combination and
validates it before deployment to real hosts. It may later become an agent
working sandbox. Linux x64 is the initial target; macOS is outside the scope.

The repository scaffold and [initial artifact pins](manifest.json) are in place.
The M1 image build and version gate are pending; no container is published yet.

## Gate policy

The following changes must pass the sandbox before reaching real hosts:

- Session runtime protocol and other cross-component contracts.
- Launcher environment, hook policy, and hook setup.
- DSH runtime pins and harness minor upgrades.
- tmux upgrades and changes that bump multiple components together.

Small single-component fixes, documentation, and UI changes may deploy directly
when they do not change these contracts. M1 will establish installation and
version agreement; M2 will establish deterministic integration behavior.

## Milestones

- **M1:** pinned Ubuntu image, `make build`, `make versions`, wrong-pin rejection,
  and CI. The official Workbench owner installer requires an active systemd user
  manager, so container installation must resolve that boundary first.
- **M2:** deterministic integration tests with fake providers.
- **M3:** `make gate CANDIDATE=<component>@<version>`.
- **M4:** a live local-model smoke run.

No images or releases are published by the scaffold workflow. See
[DEVELOPMENT.md](DEVELOPMENT.md) for contributor validation and the
[development log](docs/devlog/README.md) for completed changes.
