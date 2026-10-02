# Integration scenarios

Reserved for M2 deterministic scenarios with fake providers. Each scenario will
run in the pinned image. Candidate manifests can select nils-cli artifacts and
agent-runtime-kit source revisions independently; M3 will add the `make gate
CANDIDATE=<component>@<version>` convenience entrypoint. M4 adds a live local-model
smoke run. These gates are not implemented by M1.
