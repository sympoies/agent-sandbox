#!/usr/bin/env python3
"""Run scenario scripts in disposable directories and evaluate strict JSON contracts."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile


def run_scenario(name, directory, timeout):
    result = {"scenario": name, "status": "fail"}
    try:
        contract = json.loads((directory / "expected.json").read_text())
        if not isinstance(contract, dict) or contract.get("schema_version") != 1:
            raise ValueError("unsupported contract schema_version")
        expected = contract.get("checks")
        failures = contract.get("expected_failures", {})
        if not isinstance(expected, dict) or not expected:
            raise ValueError("contract needs a nonempty checks object")
        if not isinstance(failures, dict) or not set(failures) <= set(expected):
            raise ValueError("expected_failures must name declared checks")
        for issue in failures.values():
            if not isinstance(issue, str) or not re.fullmatch(
                    r"https://github\.com/[\w.-]+/[\w.-]+/issues/[1-9][0-9]*", issue):
                raise ValueError("each expected failure needs an issue URL")
        with tempfile.TemporaryDirectory(prefix="sandbox-scenario-") as work:
            home = Path(work) / "home"
            home.mkdir()
            env = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": work,
                   "LANG": "C.UTF-8", "TZ": "UTC", "GIT_CONFIG_NOSYSTEM": "1"}
            with subprocess.Popen(["bash", str(directory / "run.sh")], cwd=work,
                                  env=env, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, start_new_session=True) as process:
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    raise ValueError("scenario script timed out")
            if stderr:
                print(stderr, file=sys.stderr, end="")
            if process.returncode:
                raise ValueError(f"scenario script exit {process.returncode}")
            actual = json.loads(stdout)
        checks = actual["checks"]
        if not isinstance(checks, dict) or set(checks) != set(expected):
            raise ValueError("reported checks must exactly match the contract")
        rows = {}
        for key, value in expected.items():
            matches = json.dumps(checks[key], sort_keys=True) == json.dumps(value, sort_keys=True)
            status = ("unexpected-pass" if matches else "expected-fail") if key in failures else (
                "pass" if matches else "fail")
            rows[key] = {"expected": value, "actual": checks[key], "status": status}
            if key in failures:
                rows[key]["issue"] = failures[key]
        result["checks"] = rows
        if "observations" in actual:
            result["observations"] = actual["observations"]
        statuses = {row["status"] for row in rows.values()}
        result["status"] = "fail" if statuses & {"fail", "unexpected-pass"} else (
            "expected-fail" if "expected-fail" in statuses else "pass")
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        result["error"] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--scenario", default="all")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--require-sandbox", action="store_true")
    args = parser.parse_args()
    report = {"schema_version": "agent-sandbox.scenarios.v1", "status": "fail", "results": []}
    try:
        if args.require_sandbox:
            if Path("/proc/1/comm").read_text().strip() != "systemd":
                raise ValueError("scenarios require systemd as PID 1")
            if {path.name for path in Path("/sys/class/net").iterdir()} != {"lo"}:
                raise ValueError("scenarios require disconnected container networking")
        if args.timeout <= 0:
            raise ValueError("timeout must be positive")
        scenarios = {}
        for root in args.root:
            if not root.is_dir():
                raise ValueError("scenario root is not a directory")
            for directory in sorted(root.iterdir()):
                if not directory.is_dir() or directory.name.startswith("."):
                    continue
                if directory.name in scenarios:
                    raise ValueError(f"duplicate scenario: {directory.name}")
                scenarios[directory.name] = directory.resolve()
        selected = sorted(scenarios) if args.scenario == "all" else [args.scenario]
        if not selected or any(name not in scenarios for name in selected):
            raise ValueError("no scenarios found or unknown selection")
        report["results"] = [run_scenario(name, scenarios[name], args.timeout) for name in selected]
        statuses = {row["status"] for row in report["results"]}
        report["status"] = "fail" if "fail" in statuses else (
            "expected-fail" if "expected-fail" in statuses else "pass")
    except (OSError, ValueError) as error:
        report["error"] = str(error)
    print(json.dumps(report, sort_keys=True))
    return int(report["status"] == "fail")


if __name__ == "__main__":
    sys.exit(main())
