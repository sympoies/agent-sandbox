"""Regression checks for the scenario contract boundary (no container required)."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ScenarioRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def scenario(self, name, checks=None, expected=None, failures=None, script=None):
        directory = self.root / name
        directory.mkdir()
        contract = {"schema_version": 1, "checks": expected or {"works": True},
                    "expected_failures": failures or {}}
        (directory / "expected.json").write_text(json.dumps(contract))
        payload = json.dumps({"checks": checks if checks is not None else {"works": True}})
        (directory / "run.sh").write_text(script or f"#!/bin/sh\nprintf '%s\\n' '{payload}'\n")
        return directory

    def run_scenarios(self, *args):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/scenarios.py"),
                                 "--root", str(self.root), *args], capture_output=True, text=True)
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_selection_and_sorted_discovery(self):
        self.scenario("beta")
        self.scenario("alpha")
        status, result = self.run_scenarios()
        self.assertEqual(status, 0, result)
        self.assertEqual([row["scenario"] for row in result["results"]], ["alpha", "beta"])
        status, result = self.run_scenarios("--scenario", "beta")
        self.assertEqual(status, 0, result)
        self.assertEqual([row["scenario"] for row in result["results"]], ["beta"])

    def test_contract_mismatch_and_missing_check_fail(self):
        for checks in ({"works": False}, {}, {"works": 1}, {"works": True, "extra": True}):
            with self.subTest(checks=checks):
                directory = self.scenario("bad", checks=checks)
                status, result = self.run_scenarios()
                self.assertEqual(status, 1, result)
                self.assertEqual(result["status"], "fail")
                for path in directory.iterdir():
                    path.unlink()
                directory.rmdir()

    def test_issue_linked_expected_failure_and_unexpected_pass(self):
        directory = self.scenario("known", checks={"works": False},
                                  failures={"works": "https://github.com/example/tool/issues/1"})
        status, result = self.run_scenarios()
        self.assertEqual(status, 0, result)
        self.assertEqual(result["results"][0]["status"], "expected-fail")
        (directory / "run.sh").write_text("printf '%s\\n' '{\"checks\":{\"works\":true}}'\n")
        status, result = self.run_scenarios()
        self.assertEqual(status, 1, result)
        self.assertEqual(result["results"][0]["checks"]["works"]["status"], "unexpected-pass")

    def test_crash_cannot_be_expected_failure(self):
        self.scenario("crash", failures={"works": "https://github.com/example/tool/issues/1"},
                      script="exit 7\n")
        status, result = self.run_scenarios()
        self.assertEqual(status, 1, result)
        self.assertIn("exit 7", result["results"][0]["error"])

    def test_malformed_output_and_invalid_contract_fail(self):
        directory = self.scenario("broken", script="echo invalid\n")
        self.assertEqual(self.run_scenarios()[0], 1)
        (directory / "expected.json").write_text('{"schema_version":1,"checks":{}}')
        self.assertEqual(self.run_scenarios()[0], 1)

    def test_nonobject_contract_reports_json_failure(self):
        directory = self.scenario("broken")
        (directory / "expected.json").write_text("[]")
        self.assertEqual(self.run_scenarios()[0], 1)

    def test_timeout_stops_descendants(self):
        marker = self.root / "leaked-child"
        self.scenario("slow", script=f"(sleep 0.3; touch '{marker}') & wait\n")
        self.assertEqual(self.run_scenarios("--timeout", "0.05")[0], 1)
        import time
        time.sleep(0.4)
        self.assertFalse(marker.exists(), "timed-out scenario left a live child")

    def test_sandbox_prerequisite_refuses_wrong_pid1_and_connected_network(self):
        spec = importlib.util.spec_from_file_location("scenarios", ROOT / "scripts/scenarios.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for pid1, interfaces in (("sleep", []), ("systemd", [Path("lo"), Path("eth0")])):
            with self.subTest(pid1=pid1), patch.object(sys, "argv", ["scenarios.py", "--root",
                    str(self.root), "--require-sandbox"]), patch.object(Path, "read_text",
                    return_value=pid1), patch.object(Path, "iterdir", return_value=interfaces):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(runner.main(), 1)
                self.assertEqual(json.loads(output.getvalue())["status"], "fail")

    def test_unknown_selection_empty_root_and_duplicate_names_fail(self):
        self.assertEqual(self.run_scenarios()[0], 1)
        self.scenario("known")
        self.assertEqual(self.run_scenarios("--scenario", "missing")[0], 1)
        extra = self.root / "extra"
        extra.mkdir()
        (extra / "known").mkdir()
        self.assertEqual(self.run_scenarios("--root", str(extra))[0], 1)

    def test_timeout_fails_and_workspace_is_isolated(self):
        directory = self.scenario("slow", script="sleep 5\n")
        self.assertEqual(self.run_scenarios("--timeout", "0.05")[0], 1)
        (directory / "run.sh").write_text(
            'test "$HOME" != /root && test -d "$HOME" && '
            'test -z "${GIT_DIR:-}" && printf \'%s\\n\' \'{"checks":{"works":true}}\'\n')
        self.assertEqual(self.run_scenarios()[0], 0)


if __name__ == "__main__":
    unittest.main()
