#!/usr/bin/env python3
"""Exercise packaging with an isolated ELF fixture, not a production collector."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('package-collector.py')
NAME = 'agent-speed-collector-linux-x86_64'


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / 'fixture.c'
        source.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc != 2 || strcmp(argv[1], "--identity")) return 2;
    const char *identity = getenv("FIXTURE_IDENTITY");
    if (!identity) return 3;
    puts(identity);
    return 0;
}
''')
        self.binary = self.root / 'fixture'
        subprocess.run(['cc', str(source), '-o', str(self.binary)], check=True)
        self.digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps({'upstream_commit': 'fixture-upstream'}))
        self.output = self.root / 'out'

    def package(self, *options, identity=None, binary=None):
        env = dict(os.environ)
        if identity is not None:
            env['FIXTURE_IDENTITY'] = identity
        return subprocess.run([sys.executable, str(SCRIPT), str(binary or self.binary),
                               str(self.output), '--tag', 'fixture-tag',
                               '--maintenance-commit', 'fixture-commit',
                               '--config', str(self.config), *options],
                              env=env, capture_output=True, text=True)

    def test_legacy_packaging_does_not_claim_shared_capabilities(self):
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads((self.output / (NAME + '.json')).read_text())
        self.assertEqual(metadata['format_version'], 1)
        self.assertEqual(metadata['protocol']['version'], 1)
        self.assertNotIn('shared_collector', metadata['protocol'])
        self.assertEqual(metadata['sha256'], self.digest)
        self.assertEqual((self.output / (NAME + '.sha256')).read_text(), f'{self.digest}  {NAME}\n')

    def test_trusted_fixture_identity_adds_separate_control_contract(self):
        result = self.package('--verify-shared-identity', identity=f'shared-collector-v2 {self.digest}')
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads((self.output / (NAME + '.json')).read_text())
        self.assertEqual(metadata['format_version'], 1)
        self.assertEqual(metadata['protocol']['version'], 1)
        self.assertEqual(metadata['protocol']['shared_collector'], {
            'control_version': 2,
            'capabilities': ['live_activity_v2', 'live_activity_edges_v1', 'shared_collector_v1', 'widget_statistics_v2'],
            'identity': {'command': '--identity', 'prefix': 'shared-collector-v2', 'sha256': self.digest},
        })
        self.assertEqual(hashlib.sha256((self.output / NAME).read_bytes()).hexdigest(), self.digest)

    def test_missing_asset_or_wrong_identity_fails(self):
        self.assertNotEqual(self.package(binary=self.root / 'missing').returncode, 0)
        for identity in ('shared-collector-v2 ' + '0' * 64, 'wrong ' + self.digest, ''):
            with self.subTest(identity=identity):
                result = self.package('--verify-shared-identity', identity=identity)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('identity', result.stderr)
                self.assertFalse((self.output / (NAME + '.json')).exists())


if __name__ == '__main__':
    unittest.main()
