IMAGE ?= agent-sandbox:local
MANIFEST ?= manifest.json
DOCKER ?= docker
PODMAN ?= podman
CONTAINER ?=

.PHONY: build acceptance versions test check test-wrong-pin

build:
	bash scripts/build.sh "$(MANIFEST)" "$(IMAGE)" "$(DOCKER)"

# Run as a user authorized for rootful Podman (for example sudo make acceptance).
acceptance:
	bash scripts/accept.sh "$(IMAGE)" "$(DOCKER)" "$(PODMAN)"

versions:
	@test -n "$(CONTAINER)" || { echo 'Run make acceptance, or set CONTAINER to an installed booted sandbox.' >&2; exit 1; }
	$(PODMAN) cp "$(MANIFEST)" "$(CONTAINER):/opt/sandbox/expected.json"
	$(PODMAN) exec "$(CONTAINER)" python3 /opt/sandbox/scripts/versions.py /opt/sandbox/expected.json

test:
	python3 -m unittest discover -s tests -v

test-wrong-pin:
	bash scripts/test-wrong-pin.sh

check: test build acceptance
