# agent-sandbox

A Linux container project that pins an exact agent toolchain combination and
validates it before deployment to real hosts. It may later become an agent
working sandbox. Linux x64 is the initial target; macOS is outside the scope.

The [artifact manifest](manifest.json) pins the M1 toolchain. Build locally with
`make build`, then run `sudo make acceptance` on Linux with Podman and cgroup v2.
Acceptance boots a confined systemd container, runs the official Workbench
installer, and checks all versions offline, including deliberate wrong-pin
rejection. See [the development guide](DEVELOPMENT.md) for requirements.

## Gate policy

The following changes must pass the sandbox before reaching real hosts:

- Session runtime protocol and other cross-component contracts.
- Launcher environment, hook policy, and hook setup.
- DSH runtime pins and harness minor upgrades.
- tmux upgrades and changes that bump multiple components together.

Small single-component fixes, documentation, and UI changes may deploy directly
when they do not change these contracts. M1 establishes installation and
version agreement; M2 will establish deterministic integration behavior.

## Milestones

- **M1 (complete):** pinned Ubuntu image, `make build`, `make versions`, wrong-pin rejection,
  and GitHub-hosted runtime acceptance with a container-owned systemd user manager.
- **M2:** deterministic integration tests with fake providers.
- **M3:** `make gate CANDIDATE=<component>@<version>`.
- **M4:** a live local-model smoke run.

No images or releases are published by the validation workflow. See
[DEVELOPMENT.md](DEVELOPMENT.md) for contributor validation and the
[development log](docs/devlog/README.md) for completed changes.
