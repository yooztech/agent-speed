#!/usr/bin/env python3
"""Exercise release stamping against a local upstream and a real git-am queue."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("release_stamp", HERE / "release_stamp.py")
release_stamp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_stamp)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


class ReleaseStampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout"
        self.upstream = Path(self.tmp.name) / "upstream"
        self.root.mkdir()
        self.upstream.mkdir()
        git(self.upstream, "init")
        git(self.upstream, "config", "user.name", "Test")
        git(self.upstream, "config", "user.email", "test@example.invalid")
        (self.upstream / "tests").mkdir()
        (self.upstream / "VERSION").write_text("1.2.3-fork.1\n")
        (self.upstream / "tests/test_release_version.py").write_text(
            'class ReleaseVersionTests:\n'
            '    def test_fork_default_and_numeric_bundle_versions(self):\n'
            '        self.assertEqual(result.stdout.strip(), "1.2.3-fork.1|1.2.3|1.2.3")\n'
            '        template.replace("__VERSION__", "1.2.3-fork.1")\n'
            '        self.assertEqual(info["AgentSpeedVersion"], "1.2.3-fork.1")\n'
            '        template.replace("__NUMERIC_VERSION__", "1.2.3")\n'
            '        template.replace("__BUILD__", "1.2.3")\n'
            '        self.assertEqual(info["CFBundleShortVersionString"], "1.2.3")\n'
            '        self.assertEqual(info["CFBundleVersion"], "1.2.3")\n')
        git(self.upstream, "add", ".")
        git(self.upstream, "commit", "-m", "Upstream baseline")
        base = git(self.upstream, "rev-parse", "HEAD")
        (self.upstream / "feature.txt").write_text("queued change\n")
        git(self.upstream, "add", "feature.txt")
        git(self.upstream, "commit", "-m", "Add queued feature")
        patch = subprocess.run(["git", "format-patch", "-1", "--stdout"], cwd=self.upstream,
                               check=True, stdout=subprocess.PIPE).stdout
        downstream = self.root / "downstream"
        patches = downstream / "patches"
        patches.mkdir(parents=True)
        (self.root / "docs/releases").mkdir(parents=True)
        shutil.copy2(HERE / "manage.py", downstream / "manage.py")
        (downstream / "config.json").write_text(json.dumps({"upstream_url": str(self.upstream),
                                                               "upstream_commit": base}))
        name = "0001-Add-queued-feature.patch"
        (patches / name).write_bytes(patch)
        (patches / "series").write_text(name + "\n")
        (patches / "tests.json").write_text(json.dumps({name: {"regression": [], "related": [],
                                                                 "reason": "fixture"}}))
        git(self.root, "init")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Install queue")

    def test_stamp_appends_replayable_patch_and_release_notes(self):
        paths = release_stamp.stamp(self.root, "v1.2.3-fork.2")
        patches = self.root / "downstream/patches"
        names = (patches / "series").read_text().splitlines()
        self.assertEqual(len(names), 2)
        self.assertIn(Path("downstream/patches") / names[-1], paths)
        self.assertIn(names[-1], json.loads((patches / "tests.json").read_text()))
        notes = self.root / "docs/releases/v1.2.3-fork.2.md"
        self.assertIn("Add queued feature", notes.read_text())
        tree = Path(self.tmp.name) / "replayed"
        subprocess.run([os.sys.executable, str(self.root / "downstream/manage.py"),
                        "prepare", str(tree)], check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True)
        self.assertEqual((tree / "VERSION").read_text(), "1.2.3-fork.2\n")
        self.assertEqual((tree / "feature.txt").read_text(), "queued change\n")
        assertions = (tree / "tests/test_release_version.py").read_text()
        self.assertIn('"1.2.3-fork.2|1.2.3|1.2.3"', assertions)
        self.assertIn('info["AgentSpeedVersion"], "1.2.3-fork.2"', assertions)

    def test_existing_notes_are_not_overwritten(self):
        note = self.root / "docs/releases/v1.2.3-fork.2.md"
        note.write_text("existing notes\n")
        with self.assertRaises(FileExistsError):
            release_stamp.stamp(self.root, "v1.2.3-fork.2")
        self.assertEqual(note.read_text(), "existing notes\n")
        self.assertEqual(len((self.root / "downstream/patches/series").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
