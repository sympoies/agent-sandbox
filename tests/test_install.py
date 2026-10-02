"""Source archives must agree with their authenticated upstream Git tree."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SourceBindingTests(unittest.TestCase):
    def test_ignored_extra_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', '-b', 'main', directory], check=True)
            # A synthetic fixture commit; it is never delivered to a provider.
            subprocess.run(['git', '-C', directory, 'fast-import', '--quiet'], input=(
                b'blob\nmark :1\ndata 9\nignored/\n\n'
                b'commit refs/heads/main\ncommitter Fixture <fixture@example.invalid> 0 +0000\n'
                b'data 7\nfixture\nM 100644 :1 .gitignore\n\n'), check=True)
            subprocess.run(['git', '-C', directory, 'reset', '--hard', '-q', 'HEAD'], check=True)
            installer.verify_source(root)
            (root / 'ignored').mkdir()
            (root / 'ignored/extra.sh').write_text('exit 0\n')
            with self.assertRaisesRegex(ValueError, 'outside the pinned Git tree'):
                installer.verify_source(root)


if __name__ == '__main__':
    unittest.main()
