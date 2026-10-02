#!/usr/bin/env python3
"""Print observed tool versions and reject any mismatch with the candidate manifest."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

PROBES = {
    "nils-cli": (["agent-session", "--version"], r"^agent-session (\S+)"),
    "claude-code": (["claude", "--version"], r"^(\S+) \(Claude Code\)"),
    "codex": (["codex", "--version"], r"^codex-cli (\S+)"),
    "tmux": (["tmux", "-V"], r"^tmux (\S+)"),
    "node": (["node", "--version"], r"^v(\S+)"),
    "bun": (["bun", "--version"], r"^(\S+)"),
    "python": (["python3", "--version"], r"^Python (\S+)"),
}


def output(command):
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, timeout=30).strip()


def observe(name):
    if name in PROBES:
        command, pattern = PROBES[name]
        match = re.search(pattern, output(command))
        if not match:
            raise ValueError("unrecognized version output")
        return match.group(1)
    if name in {"agent-runtime-kit", "zsh-kit"}:
        root = f"/opt/{name}"
        if output(["git", "-C", root, "status", "--porcelain", "--untracked-files=no"]):
            raise ValueError("source checkout has tracked modifications")
        return output(["git", "-C", root, "rev-parse", "HEAD"])
    if name in {"dsh-workbench", "dsh-runtime-kit"}:
        root = Path("/opt/workbench")
        release_bytes = (root / "release/release-manifest.json").read_bytes()
        image_pin = json.loads(Path("/opt/sandbox/manifest.json").read_text())["components"]["dsh-workbench"]
        if hashlib.sha256(release_bytes).hexdigest() != image_pin["manifest_sha256"]:
            raise ValueError("installed release manifest checksum differs")
        release = json.loads(release_bytes)
        receipt = json.loads((root / "installed-unit-receipt.json").read_text())
        if receipt["releaseVersion"] != release["releaseVersion"]:
            raise ValueError("installed receipt differs from release")
        if name == "dsh-workbench":
            return receipt["releaseVersion"]
        package = root / "release" / release["runtimeKit"]["packagePath"]
        if hashlib.file_digest(package.open("rb"), "sha256").hexdigest() != release["runtimeKit"]["packageRawSha256"]:
            raise ValueError("runtime-kit archive differs from installed release")
        with tarfile.open(package) as archive:
            for member in archive.getmembers():
                if member.isfile():
                    installed = root / "runtime-kit" / member.name
                    if installed.read_bytes() != archive.extractfile(member).read():
                        raise ValueError("installed runtime-kit differs from release archive")
        return release["runtimeKit"]["sourceCommit"]
    raise ValueError(f"unsupported component {name}")


def main():
    manifest = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/sandbox/manifest.json").read_text())
    failed = False
    for name, pin in sorted(manifest["components"].items()):
        expected = pin["version"]
        try:
            actual = observe(name)
            suffix = "" if actual == expected else f" (expected {expected})"
            print(f"{name}: {actual}{suffix}")
            failed |= actual != expected
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            print(f"{name}: ERROR {error}")
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
