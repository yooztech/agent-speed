#!/usr/bin/env python3
"""Exercise the release zip verifier with controlled archives on Linux or macOS."""
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name('verify-collector-zip.py')
MEMBER = 'Agent Speed.app/Contents/Resources/collectors/linux-x86_64/agent-speed-collector'


class CollectorZipTests(unittest.TestCase):
    def check_archive(self, member, mode, payload=b'collector', expected_success=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / 'collector'
            expected.write_bytes(b'collector')
            archive = root / 'app.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                info = zipfile.ZipInfo(member)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | mode) << 16
                zipped.writestr(info, payload)
            result = subprocess.run([sys.executable, str(SCRIPT), str(archive), str(expected)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode == 0, expected_success, result.stderr)

    def test_missing_collector(self):
        self.check_archive('other/agent-speed-collector', 0o755)

    def test_non_executable_collector(self):
        self.check_archive(MEMBER, 0o644)

    def test_different_collector(self):
        self.check_archive(MEMBER, 0o755, b'different')

    def test_valid_collector(self):
        self.check_archive(MEMBER, 0o755, expected_success=True)


if __name__ == '__main__':
    unittest.main()
