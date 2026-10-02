# agent-sandbox

Linux toolchain validation gate. Read [DEVELOPMENT.md](DEVELOPMENT.md) before
editing; `manifest.json` owns exact component and artifact pins.

- Keep all tracked files and provider records generic and reusable. Never copy
  private deployment identities, paths, accounts, credentials, or topology.
- Preserve unrelated work. Use bounded, reversible changes and meaningful
  regression tests for observable behavior.
- Run `agent-docs preflight --intent project-dev` when available. Run
  `.agents/scripts/pre-pr.sh` before delivery.
- Use signed semantic commits in managed feature worktrees and the governed
  PR workflow. Merge only after required CI and review pass.
- This repository does not publish images or releases automatically. Publication
  requires explicit maintainer authorization.
- Keep future integration scenarios under `tests/integration/`; fake providers
  and candidate selection are later milestones.
