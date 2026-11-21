#!/usr/bin/env python3
"""Exercise clone retry cleanup without contacting the network."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('manage', HERE / 'manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class CloneRetryTests(unittest.TestCase):
    def test_transient_failure_removes_partial_before_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'checkout'
            calls = []

            def clone(args, **kwargs):
                calls.append(args)
                self.assertEqual(list(output.iterdir()), [])
                if len(calls) == 1:
                    (output / 'partial').write_text('partial')
                    raise subprocess.CalledProcessError(1, args, stderr='connection reset')
                (output / 'complete').write_text('complete')
                return ''

            with patch.object(manage.release_network, 'run_once', side_effect=clone), \
                 patch.object(manage.release_network.time, 'sleep'), patch.object(manage, 'run'):
                self.assertEqual(manage.prepare(output, 'a' * 40, []), output)
            self.assertEqual(len(calls), 2)
            self.assertTrue((output / 'complete').exists())

    def test_unclassified_clone_failure_still_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'checkout'
            calls = []

            def clone(args, **kwargs):
                calls.append(1)
                if len(calls) == 1:
                    raise subprocess.CalledProcessError(
                        128, args, stderr="fatal: unable to access 'https://github.com/': unknown transport failure")
                (output / 'complete').write_text('complete')
                return ''

            with patch.object(manage.release_network, 'run_once', side_effect=clone), \
                 patch.object(manage.release_network.time, 'sleep'), patch.object(manage, 'run'):
                self.assertEqual(manage.prepare(output, 'a' * 40, []), output)
            self.assertEqual(len(calls), 2)

    def test_permanent_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'checkout'

            def clone(args, **kwargs):
                (output / 'partial').write_text('partial')
                raise subprocess.CalledProcessError(1, args, stderr='authentication failed')

            with patch.object(manage.release_network, 'run_once', side_effect=clone) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    manage.prepare(output, 'a' * 40, [])
            self.assertEqual(run.call_count, 1)
            self.assertFalse(output.exists())

    def test_preexisting_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'checkout'
            output.mkdir()
            marker = output / 'user-data'
            marker.write_text('keep')
            with patch.object(manage.release_network, 'run_once') as run:
                with self.assertRaises(ValueError):
                    manage.prepare(output, 'a' * 40, [])
            run.assert_not_called()
            self.assertEqual(marker.read_text(), 'keep')

    def test_am_failure_recreates_tree_and_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'checkout'
            clones = []
            am_calls = []

            def clone(args, **kwargs):
                clones.append(args)
                (output / 'state').write_text('fresh')
                return ''

            def run(args, cwd=None, **kwargs):
                if 'am' in args:
                    am_calls.append(args)
                    if len(am_calls) == 1:
                        raise subprocess.CalledProcessError(
                            1, args, stderr='unable to create temporary file: No such file or directory')
                return ''

            with patch.object(manage.release_network, 'run_once', side_effect=clone), \
                 patch.object(manage, 'run', side_effect=run), \
                 patch.object(manage.time, 'sleep') as sleep:
                self.assertEqual(manage.prepare(output, 'a' * 40, ['0001-test.patch']), output)

            self.assertEqual(len(clones), 2)
            self.assertEqual(len(am_calls), 2)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 1, 1])
            self.assertTrue((output / 'state').exists())

    def test_repeated_am_failure_stops_after_one_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'checkout'
            clones = []

            def clone(args, **kwargs):
                clones.append(args)
                (output / 'state').write_text('fresh')
                return ''

            def run(args, cwd=None, **kwargs):
                if 'am' in args:
                    raise subprocess.CalledProcessError(1, args, stderr='unable to create temporary file')
                return ''

            with patch.object(manage.release_network, 'run_once', side_effect=clone), \
                 patch.object(manage, 'run', side_effect=run), \
                 patch.object(manage.time, 'sleep'):
                with self.assertRaises(subprocess.CalledProcessError):
                    manage.prepare(output, 'a' * 40, ['0001-test.patch'])

            self.assertEqual(len(clones), 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
