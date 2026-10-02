ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS dependencies
ARG UBUNTU_SNAPSHOT
ARG CA_URL
ARG CA_SHA256
ADD --checksum=sha256:${CA_SHA256} ${CA_URL} /tmp/ca.deb
RUN dpkg-deb -x /tmp/ca.deb /tmp/ca && \
    mkdir -p /etc/ssl/certs && \
    cat /tmp/ca/usr/share/ca-certificates/mozilla/*.crt > /etc/ssl/certs/ca-certificates.crt && \
    rm -rf /tmp/ca /tmp/ca.deb
ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/python/bin:/opt/node/bin:/usr/local/bin:/usr/bin:/bin \
    LANG=C.UTF-8
# Immutable signed Ubuntu snapshot supplies build and runtime dependencies.
RUN test -n "$UBUNTU_SNAPSHOT" && \
    rm /etc/apt/sources.list.d/ubuntu.sources && \
    printf 'deb https://snapshot.ubuntu.com/ubuntu/%s noble main universe\ndeb https://snapshot.ubuntu.com/ubuntu/%s noble-updates main universe\ndeb https://snapshot.ubuntu.com/ubuntu/%s noble-security main universe\n' \
      "$UBUNTU_SNAPSHOT" "$UBUNTU_SNAPSHOT" "$UBUNTU_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get -o Acquire::Check-Valid-Until=false -o APT::Update::Error-Mode=any update && \
    apt-get install -y --no-install-recommends ca-certificates curl git xz-utils unzip \
      build-essential pkg-config libevent-dev libncurses-dev bison libssl-dev \
      zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev \
      python3 ripgrep jq procps zsh systemd systemd-sysv dbus-user-session make && \
    rm -rf /var/lib/apt/lists/*
FROM dependencies
WORKDIR /opt/sandbox
# Use separate COPY destinations to preserve the runtime test layout.
COPY manifest.json /opt/sandbox/manifest.json
COPY scripts/install.py /opt/sandbox/scripts/install.py
# Container-owned user manager, started directly as root without a host login.
# PAM loginuid cannot change the inherited host audit identity in confinement.
RUN mkdir -p /etc/systemd/system/user@0.service.d && \
    printf '[Service]\nPAMName=\nEnvironment=XDG_RUNTIME_DIR=/run/user/0\n' \
      > /etc/systemd/system/user@0.service.d/20-container.conf
RUN /usr/bin/python3 scripts/install.py prepare
COPY scripts/ /opt/sandbox/scripts/
COPY tests/ /opt/sandbox/tests/
COPY Makefile /opt/sandbox/Makefile
ENV container=podman
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
