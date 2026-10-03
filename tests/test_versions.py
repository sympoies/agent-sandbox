"""Exercise the version gate using a disposable tool installation."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VersionGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        outputs = {
            "agent-session": "agent-session 1.2.3 (v1.2.3, rustc test)",
            "claude": "2.3.4 (Claude Code)", "codex": "codex-cli 3.4.5",
            "tmux": "tmux 3.4", "node": "v24.0.0", "bun": "1.2.3",
            "python3": "Python 3.12.3",
        }
        for name, output in outputs.items():
            self.tool(name, output)
        self.manifest = {"components": {
            "nils-cli": {"version": "1.2.3"},
            "claude-code": {"version": "2.3.4"},
            "codex": {"version": "3.4.5"}, "tmux": {"version": "3.4"},
            "node": {"version": "24.0.0"}, "bun": {"version": "1.2.3"},
            "python": {"version": "3.12.3"},
        }}

    def tool(self, name, output, status=0):
        path = self.bin / name
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\nexit {status}\n")
        path.chmod(0o755)

    def run_gate(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(self.manifest))
        return subprocess.run(
            [os.sys.executable, str(ROOT / "scripts/versions.py"), str(manifest)],
            env={**os.environ, "PATH": str(self.bin)}, text=True, capture_output=True,
        )

    def test_matching_versions_pass(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("node: 24.0.0", result.stdout)

    def test_wrong_pin_fails_and_still_reports_other_tools(self):
        self.manifest["components"]["node"]["version"] = "0.0.0"
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 0.0.0", result.stdout)
        self.assertIn("tmux: 3.4", result.stdout)

    def test_missing_tool_fails(self):
        (self.bin / "bun").unlink()
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bun: ERROR", result.stdout)

    def test_failed_probe_cannot_pass_with_matching_output(self):
        self.tool("node", "v24.0.0", 1)
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("node: ERROR", result.stdout)


if __name__ == "__main__":
    unittest.main()
