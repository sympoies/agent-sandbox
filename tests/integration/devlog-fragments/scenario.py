"""Exercise the released devlog against disposable clones of a local bare remote."""
from datetime import date, timedelta
import json
import os
from pathlib import Path
import subprocess

KIT = os.environ.get("AGENT_SANDBOX_KIT_CANDIDATE")
if KIT:
    # Derive the tool environment from the candidate kit, not a scenario override.
    env = {**os.environ, "AGENT_RUNTIME_DEVLOG_FRAGMENTS": "1"}
    rendered = subprocess.run(["bash", str(Path(KIT) / "scripts/render-runtime-env.sh")],
                              env=env, text=True, capture_output=True, check=True).stdout
    selected = subprocess.run(["bash", "-c", rendered + '\nprintf %s "$DEVLOG_LAYOUT"'],
                              env=env, text=True, capture_output=True, check=True).stdout
    os.environ["DEVLOG_LAYOUT"] = selected
else:
    os.environ["DEVLOG_LAYOUT"] = "fragments"
ROOT = Path.cwd()
REMOTE = ROOT / "remote.git"
TODAY = date.today()
checks = {}
observations = {}


def command(repo, *args, ok=True):
    result = subprocess.run(args, cwd=repo, text=True, capture_output=True, timeout=30)
    if ok and result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed: {result.stdout}{result.stderr}")
    return result


def git(repo, *args, ok=True):
    return command(repo, "git", *args, ok=ok)


def devlog(repo, action, *args, ok=True):
    result = command(repo, "devlog", action, *args, "--format", "json", ok=ok)
    return result, json.loads(result.stdout)


def clone(name):
    repo = ROOT / name
    git(ROOT, "clone", str(REMOTE), str(repo))
    git(repo, "config", "user.name", "Scenario Maintainer")
    git(repo, "config", "user.email", "maintainer@example.invalid")
    # Fixture commits exercise local Git transport, not provider signing policy.
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "config", "core.hooksPath", "/dev/null")
    return repo


def commit(repo, title):
    git(repo, "add", "--all")
    git(repo, "commit", "-m", title)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def entry(repo, slug, day="2001-01-01"):
    devlog(repo, "new", "--title", f"Scenario {slug}", "--slug", slug, "--date", day,
           "--result", f"Recorded {slug} result.", "--why", "Independent changes need isolated entries.",
           "--evidence", "Local bare-remote scenario.")


def check_result(repo, *args):
    if KIT:
        env = {**os.environ, "DEVLOG_CHECK_BASE": "origin/main"}
        result = subprocess.run(["bash", str(Path(KIT) / "scripts/ci/devlog-check.sh"),
                                 "--format", "json", *args], cwd=repo, env=env,
                                text=True, capture_output=True, timeout=30)
        return result, json.loads(result.stdout)
    return devlog(repo, "check", "--base", "origin/main", *args, ok=False)


def check(repo):
    result, payload = check_result(repo)
    return result.returncode == 0, payload


def fold_commit(repo):
    _, payload = devlog(repo, "fold")
    passed, _ = check(repo)
    if not passed:
        raise RuntimeError("devlog check rejected folded content")
    git(repo, "add", "--all", "docs/devlog")
    changed = git(repo, "diff", "--cached", "--quiet", ok=False).returncode
    if changed == 1:
        git(repo, "commit", "-m", "Fold eligible development log fragments")
    elif changed != 0:
        raise RuntimeError("unable to inspect staged fold")
    return payload, changed == 1


git(ROOT, "init", "--bare", "--initial-branch=main", str(REMOTE))
seed = clone("seed")
log = seed / "docs/devlog"
log.mkdir(parents=True)
(log / "README.md").write_text("# Development log\n\n## Months\n")
git(seed, "commit", "--allow-empty", "-m", "Initialize scenario repository")
devlog(seed, "index")
entry(seed, "today", TODAY.isoformat())
entry(seed, "future", (TODAY + timedelta(days=7)).isoformat())
commit(seed, "Seed pending entries")
git(seed, "push", "--set-upstream", "origin", "main")
git(seed, "remote", "set-head", "origin", "--auto")
base = git(seed, "rev-parse", "HEAD").stdout.strip()
_, created = fold_commit(seed)
checks["noop_no_commit"] = not created and git(seed, "rev-parse", "HEAD").stdout.strip() == base
checks["noop_clean_tree"] = not git(seed, "status", "--porcelain").stdout.strip()

shared_before = (log / "README.md").read_bytes()
for slug in ("alpha", "beta"):
    git(seed, "checkout", "-b", slug, base)
    entry(seed, slug)
    checks[f"{slug}_isolated_fragment"] = (
        (log / "pending" / f"2001-01-01-{slug}.md").is_file()
        and (log / "README.md").read_bytes() == shared_before
        and not (log / "2001-01.md").exists())
    commit(seed, f"Add {slug} fragment")
    git(seed, "push", "origin", slug)

merged = []
for order in (("alpha", "beta"), ("beta", "alpha")):
    repo = clone("merge-" + "-".join(order))
    for slug in order:
        result = git(repo, "merge", "--no-ff", "--no-edit", f"origin/{slug}", ok=False)
        passed, _ = check(repo)
        checks[f"merge_{'-'.join(order)}_{slug}"] = result.returncode == 0 and passed
    merged.append(repo)
git(merged[0], "push", "origin", "main")

# Independent clones must fold identical content to identical bytes.
folded_bytes = []
for repo in merged:
    payload, created = fold_commit(repo)
    month = repo / "docs/devlog/2001-01.md"
    text = month.read_text()
    checks[f"normal_fold_{repo.name}"] = (
        created and payload["data"]["folded"] == 2
        and text.count("## 2001-01-01 - Scenario alpha") == 1
        and text.count("## 2001-01-01 - Scenario beta") == 1
        and text.index("Scenario alpha") < text.index("Scenario beta")
        and not (repo / "docs/devlog/pending/2001-01-01-alpha.md").exists()
        and not (repo / "docs/devlog/pending/2001-01-01-beta.md").exists()
        and len(list((repo / "docs/devlog/pending").glob("*.md"))) == 2
        and "[2001-01](2001-01.md)" in (repo / "docs/devlog/README.md").read_text())
    folded_bytes.append((month.read_bytes(), (repo / "docs/devlog/README.md").read_bytes()))
    head = git(repo, "rev-parse", "HEAD").stdout
    payload, created = fold_commit(repo)
    checks[f"idempotent_{repo.name}"] = (
        not created and payload["data"]["folded"] == 0
        and git(repo, "rev-parse", "HEAD").stdout == head
        and not git(repo, "status", "--porcelain").stdout.strip())
checks["deterministic_fold"] = folded_bytes[0] == folded_bytes[1]

# Advance the remote after the worker's fold commit; actual transport rejects it.
worker = merged[0]
racer = clone("concurrent-writer")
entry(racer, "gamma")
commit(racer, "Add concurrent fragment")
git(racer, "push", "origin", "main")
remote_tip = git(racer, "rev-parse", "HEAD").stdout.strip()
rejection = git(worker, "push", "origin", "main", ok=False)
checks["stale_push_rejected"] = rejection.returncode != 0 and (
    "[rejected]" in rejection.stderr and ("fetch first" in rejection.stderr or "non-fast-forward" in rejection.stderr))
# Discard only the disposable clone's unpushed fold, then rerun on the fetched tip.
git(worker, "fetch", "origin", "main")
git(worker, "reset", "--hard", "origin/main")
checks["retry_fetched_tip"] = git(worker, "rev-parse", "HEAD").stdout.strip() == remote_tip
payload, created = fold_commit(worker)
retry = git(worker, "push", "origin", "main", ok=False)
month = worker / "docs/devlog/2001-01.md"
text = month.read_text()
checks["retry_fold_push"] = created and payload["data"]["folded"] == 3 and retry.returncode == 0
checks["retry_preserves_all_entries"] = all(text.count(f"## 2001-01-01 - Scenario {slug}") == 1
                                               for slug in ("alpha", "beta", "gamma"))
checks["retry_remote_matches"] = git(worker, "ls-remote", "origin", "refs/heads/main").stdout.split()[0] == (
    git(worker, "rev-parse", "HEAD").stdout.strip())
git(worker, "fetch", "origin", "main")
checks["check_after_retry"] = check(worker)[0]

# PRs may add fragments; the trusted fold remains the month-file writer.
git(worker, "checkout", "-b", "month-correction")
month.write_text(text.replace("Recorded alpha result.", "Corrected alpha result."))
commit(worker, "Correct folded month result")
result, payload = check_result(worker, "--fragments-only")
problems = payload.get("error", {}).get("details", {}).get("problems", [])
month_rejected = result.returncode == 65 and any(
    problem.get("kind") == "month-file-changed" for problem in problems)
checks["month_edit_check"] = ("rejected" if month_rejected else
                              "accepted" if result.returncode == 0 else "unexpected-rejection")
observations["month_edit"] = {"exit_code": result.returncode, "check": payload}
git(worker, "checkout", "main")
git(worker, "checkout", "-b", "fragment-edit")
today_fragment = worker / "docs/devlog/pending" / f"{TODAY.isoformat()}-today.md"
today_fragment.write_text(today_fragment.read_text().replace("Recorded today result.", "Changed today result."))
commit(worker, "Edit merged pending fragment")
passed, payload = check(worker)
checks["merged_fragment_edit_rejected"] = not passed and "fragment-modified" in json.dumps(payload)
observations["fragment_edit"] = payload
if KIT:
    checks["kit_switch_on_selects_fragments"] = os.environ["DEVLOG_LAYOUT"] == "fragments"
    for setting in (None, "0"):
        env = dict(os.environ)
        env.pop("AGENT_RUNTIME_DEVLOG_FRAGMENTS", None)
        if setting is not None:
            env["AGENT_RUNTIME_DEVLOG_FRAGMENTS"] = setting
        rendered = subprocess.run(["bash", str(Path(KIT) / "scripts/render-runtime-env.sh")],
                                  env=env, text=True, capture_output=True, check=True).stdout
        checks["kit_switch_off_" + (setting or "unset")] = rendered == ":\n"
    checks["kit_check_accepts_merged_fragments"] = check(seed)[0]
    observations["kit_candidate"] = "environment render and check owner exercised"
print(json.dumps({"checks": checks, "observations": observations}, sort_keys=True))
