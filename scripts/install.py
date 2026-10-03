#!/usr/bin/env python3
"""Install authenticated official artifacts into the disposable Linux image."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

WORK = Path("/opt/build")
BIN = Path("/usr/local/bin")


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def download(name, pin):
    path = WORK / (name + ".archive")
    run("curl", "--fail", "--location", "--retry", "3", "--silent", "--show-error", pin["url"], "-o", str(path))
    if hashlib.file_digest(path.open("rb"), "sha256").hexdigest() != pin["sha256"]:
        raise ValueError(f"checksum mismatch: {name}")
    return path


def extract(path, root, strip=True):
    root.mkdir(parents=True, exist_ok=True)
    run("tar", "-xf", str(path), "-C", str(root), *( ["--strip-components=1"] if strip else []))


def verify_source(root):
    run("git", "-C", str(root), "diff", "--exit-code", "HEAD")
    for extra_flags in ([], ["--ignored"]):
        extras = subprocess.check_output(["git", "-C", str(root), "ls-files", "--others",
                                          "--exclude-standard", *extra_flags], text=True)
        if extras:
            raise ValueError("source archive contains files outside the pinned Git tree")


def source(name, pin):
    root = Path("/opt") / name
    extract(download(name, pin), root)
    # Bind the source archive to the actual upstream Git object, preserving the
    # authenticated archive bytes and detecting any disagreement with that tree.
    run("git", "init", "-q", str(root))
    run("git", "-C", str(root), "fetch", "-q", "--depth=1", pin["repository"], pin["version"])
    run("git", "-C", str(root), "reset", "--mixed", "-q", "FETCH_HEAD")
    verify_source(root)
    return root


def prepare():
    manifest = json.loads(Path("/opt/sandbox/manifest.json").read_text())
    WORK.mkdir(mode=0o700)
    pins = manifest["components"]
    extract(download("node", pins["node"]), Path("/opt/node"))
    with zipfile.ZipFile(download("bun", pins["bun"])) as archive:
        archive.extractall(WORK / "bun-unpacked")
    shutil.copyfile(WORK / "bun-unpacked/bun-linux-x64/bun", BIN / "bun")
    (BIN / "bun").chmod(0o755)
    extract(download("nils-cli", pins["nils-cli"]), WORK / "nils")
    for binary in (WORK / "nils/bin").iterdir():
        shutil.copy2(binary, BIN / binary.name)
    extract(download("codex", pins["codex"]), WORK / "codex", strip=False)
    shutil.copy2(WORK / "codex/codex-x86_64-unknown-linux-musl", BIN / "codex")
    extract(download("claude-code", pins["claude-code"]), WORK / "claude")
    shutil.copy2(WORK / "claude/claude", BIN / "claude")
    (BIN / "claude").chmod(0o755)
    extract(download("python", pins["python"]), WORK / "python")
    run("./configure", "--prefix=/opt/python", "--with-ensurepip=no", cwd=WORK / "python")
    run("make", "-j4", cwd=WORK / "python")
    run("make", "install", cwd=WORK / "python")
    extract(download("tmux", pins["tmux"]), WORK / "tmux")
    run("./configure", "--prefix=/usr/local", cwd=WORK / "tmux")
    run("make", "-j4", cwd=WORK / "tmux")
    run("make", "install", cwd=WORK / "tmux")
    kit = source("agent-runtime-kit", pins["agent-runtime-kit"])
    for product in ("codex", "claude"):
        run("agent-runtime", "render", "--source-root", str(kit), "--product", product)
        run("agent-runtime", "install", "--source-root", str(kit), "--product", product,
            "--live-home", f"/root/.{product}", "--state-home", "/root/.local/state/agent-runtime-kit", "--no-overlay", "--apply")
    source("zsh-kit", pins["zsh-kit"])
    dsh_kit = source("dsh-runtime-kit", pins["dsh-runtime-kit"])
    wb = pins["dsh-workbench"]
    wb_source_pin = wb["source"]
    wb_source = source("workbench-source", wb_source_pin)
    pnpm_root = WORK / "pnpm"
    extract(download("pnpm", manifest["build_tools"]["pnpm"]), pnpm_root)
    pnpm_bin = pnpm_root / "bin/pnpm.cjs"
    archive = download("workbench.tar.gz", wb)
    owner = Path("/opt/workbench-owner.json")
    owner.write_text(json.dumps({"schemaVersion": "dsh-workbench.owner-environment.v1", "environment": {}, "secretFiles": {}}))
    owner.chmod(0o600)
    # Use the official owner's complete-package hash function, then the normal
    # no-write plan / digest-bound apply installer. No provider credentials enter
    # this image, and the release's frozen dependency graph is kept unchanged.
    hash_js = f"import {{ownerPackageTreeSha256}} from '{wb_source}/src/linux-owner-input.ts'; console.log(ownerPackageTreeSha256('{pnpm_root}', '{pnpm_bin}'));"
    package_hash = subprocess.check_output(["node", "--input-type=module", "-e", hash_js], text=True).strip()
    inputs = {
        "schemaVersion": "dsh-workbench.linux-install-input.v1",
        "archivePath": str(archive), "archiveSha256": wb["sha256"], "manifestSha256": wb["manifest_sha256"],
        "runtimeKitRepo": str(dsh_kit), "pnpmExecutable": str(pnpm_bin),
        "pnpmSha256": hashlib.file_digest(pnpm_bin.open("rb"), "sha256").hexdigest(),
        "pnpmPackageRoot": str(pnpm_root), "pnpmPackageSha256": package_hash,
        "installRoot": "/opt/workbench", "ownerEnvironmentFile": str(owner),
    }
    input_path = WORK / "workbench-input.json"
    input_path.write_text(json.dumps(inputs))
    input_path.chmod(0o600)
    # The official installed package-manager shims retain this package root.
    retained = {"pnpm", "workbench.tar.gz.archive", "workbench-input.json"}
    for path in WORK.iterdir():
        if path.name not in retained:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    for name in ("workbench-web", "workbench-tui"):
        (BIN / name).symlink_to(Path("/opt/workbench/bin") / name)


def finish():
    # Invoke the unchanged authenticated owner installer only after systemd boots.
    wb_source = Path("/opt/workbench-source")
    verify_source(wb_source)
    command = ["node", str(wb_source / "scripts/linux-install.mjs")]
    input_path = WORK / "workbench-input.json"
    plan = json.loads(subprocess.check_output([*command, "plan", str(input_path)], text=True, cwd=wb_source))
    run(*command, "apply", str(input_path), plan["planDigest"], cwd=wb_source)


if __name__ == "__main__":
    {"prepare": prepare, "finish": finish}[sys.argv[1]]()
