#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import release_network

spec = importlib.util.spec_from_file_location('publish_release', Path(__file__).with_name('publish-release.py'))
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class FakeGitHub:
    def __init__(self):
        self.release = None
        self.assets = {}
        self.lost = set()
        self.writes = []
        self.query_failure = None
        self.fail_before = {}
        self.upload_conflict = False

    def read(self, args, **kwargs):
        def query():
            if self.query_failure:
                error, self.query_failure = self.query_failure, None
                raise subprocess.CalledProcessError(1, args, stderr=error)
            endpoint = args[-1]
            if '/git/ref/tags/' in endpoint:
                result = {'object': {'type': 'commit', 'sha': 'a' * 40}}
            elif '/assets?' in endpoint:
                result = [list(self.assets.values())]
            elif '/releases?' in endpoint:
                result = [[self.release] if self.release else []]
            else:
                raise AssertionError(endpoint)
            return json.dumps(result)
        return release_network.retry(query, label='query')

    def write(self, args, **kwargs):
        action = args[2]
        self.writes.append(action)
        if self.fail_before.get(action, 0):
            self.fail_before[action] -= 1
            raise subprocess.CalledProcessError(1, args, stderr='connection reset')
        if '--clobber' in args:
            raise AssertionError('Release assets must never be clobbered')
        if action == 'create':
            self.release = {'id': 1, 'tag_name': 'v1.2.3-fork.1', 'draft': True, 'prerelease': False}
        elif action == 'upload':
            path = Path(args[4])
            data = path.read_bytes()
            self.assets[path.name] = {'name': path.name, 'size': len(data), 'state': 'uploaded',
                                      'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}
            if self.upload_conflict:
                raise subprocess.CalledProcessError(1, args, stderr='HTTP 422 already_exists')
        elif action == 'edit':
            self.release['draft'] = False
        else:
            raise AssertionError(action)
        if action in self.lost:
            self.lost.remove(action)
            raise subprocess.CalledProcessError(1, args, stderr='connection reset')
        return ''


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        old = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, old)
        Path('dist').mkdir()
        Path('dist/asset').write_bytes(b'contents')
        self.github = FakeGitHub()
        for patcher in (
            patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_REF_NAME': 'v1.2.3-fork.1',
                                    'GITHUB_SHA': 'a' * 40}),
            patch.object(publish.release, 'assets_expected', return_value={'asset'}),
            patch.object(release_network, 'run', side_effect=self.github.read),
            patch.object(release_network, 'run_once', side_effect=self.github.write),
            patch.object(release_network.time, 'sleep'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_lost_create_upload_and_publication_responses(self):
        self.github.lost = {'create', 'upload', 'edit'}
        publish.main()
        self.assertEqual(self.github.writes, ['create', 'upload', 'edit'])
        self.assertFalse(self.github.release['draft'])

    def test_final_attempt_accepted_response_is_reconciled(self):
        self.github.fail_before = {'create': 3, 'upload': 3, 'edit': 3}
        self.github.lost = {'create', 'upload', 'edit'}
        publish.main()
        for action in ('create', 'upload', 'edit'):
            self.assertEqual(self.github.writes.count(action), 4)
        self.assertFalse(self.github.release['draft'])

    def test_concurrent_matching_upload_is_accepted(self):
        self.github.upload_conflict = True
        publish.main()
        self.assertEqual(self.github.writes, ['create', 'upload', 'edit'])

    def test_conflicting_asset_is_never_overwritten(self):
        self.github.release = {'id': 1, 'tag_name': 'v1.2.3-fork.1', 'draft': True, 'prerelease': False}
        self.github.assets['asset'] = {'name': 'asset', 'size': 1, 'state': 'uploaded', 'digest': 'sha256:other'}
        with self.assertRaisesRegex(RuntimeError, 'Conflicting asset'):
            publish.main()
        self.assertEqual(self.github.writes, [])

    def test_transient_query_is_retried(self):
        self.github.query_failure = 'HTTP 503'
        publish.main()
        self.assertEqual(self.github.writes, ['create', 'upload', 'edit'])

    def test_published_release_is_untouched_even_without_dist(self):
        self.github.release = {'id': 1, 'tag_name': 'v1.2.3-fork.1', 'draft': False}
        Path('dist/asset').unlink()
        Path('dist').rmdir()
        publish.main()
        self.assertEqual(self.github.writes, [])

    def test_auth_failure_is_fatal(self):
        self.github.query_failure = 'HTTP 401 unauthorized'
        with self.assertRaises(subprocess.CalledProcessError):
            publish.main()
        self.assertEqual(self.github.writes, [])

    def test_matching_existing_asset_is_not_reuploaded(self):
        self.github.release = {'id': 1, 'tag_name': 'v1.2.3-fork.1', 'draft': True, 'prerelease': False}
        data = b'contents'
        self.github.assets['asset'] = {'name': 'asset', 'size': len(data), 'state': 'uploaded',
                                       'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}
        publish.main()
        self.assertEqual(self.github.writes, ['edit'])


if __name__ == '__main__':
    unittest.main()
