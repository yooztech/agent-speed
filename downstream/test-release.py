#!/usr/bin/env python3
"""Exercise release selection and race safeguards with local Git remotes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("release_driver", HERE / "release.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


class FakeAPI:
    def __init__(self, baseline, releases, active=False, publish_on_cancel=False,
                 publish_on_delete=False, fail=None):
        self.baseline = baseline
        self.releases = releases
        self.active = active
        self.publish_on_cancel = publish_on_cancel
        self.publish_on_delete = publish_on_delete
        self.fail = fail
        self.calls = []

    def __call__(self, path, method="GET"):
        self.calls.append((method, path))
        if self.fail and self.fail in path:
            raise subprocess.CalledProcessError(1, ["gh", "api", path])
        if path.endswith("/releases/latest"):
            return {"tag_name": "v1.2.3"}
        if "/git/ref/tags/" in path:
            return {"object": {"type": "commit", "sha": self.baseline}}
        if "/actions/workflows/" in path:
            return {"workflow_runs": ([{"id": 42, "status": "in_progress",
                                         "head_branch": "v1.2.3-fork.2"}]
                                       if self.active else [])}
        if path.endswith("/actions/runs/42/cancel"):
            if self.publish_on_cancel:
                self.releases.append({"id": 99, "tag_name": "v1.2.3-fork.2",
                                      "draft": False, "prerelease": False})
            self.active = False
            return None
        if path.endswith("/actions/runs/42"):
            return {"status": "completed"}
        if "/releases?" in path:
            return list(self.releases)
        if "/releases/" in path and method == "DELETE":
            ident = int(path.rsplit("/", 1)[1])
            if self.publish_on_delete:
                self.releases.append({"id": 99, "tag_name": "v1.2.3-fork.2",
                                      "draft": False, "prerelease": False})
            self.releases[:] = [r for r in self.releases if r["id"] != ident]
            return None
        raise AssertionError(f"unexpected API request: {method} {path}")


class ReleaseDriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout"
        self.remote = Path(self.tmp.name) / "origin.git"
        self.root.mkdir()
        git(self.root, "init", "--initial-branch=downstream/patch-build")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "downstream").mkdir()
        self.baseline = "a" * 40
        (self.root / "downstream/config.json").write_text(json.dumps({
            "upstream_version": "1.2.3", "upstream_commit": self.baseline}))
        (self.root / "file").write_text("old\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Old")
        self.old = git(self.root, "rev-parse", "HEAD")
        git(self.root, "tag", "v1.2.3-fork.1")
        git(self.root, "tag", "v1.2.3-fork.2")
        (self.root / "file").write_text("latest\n")
        git(self.root, "commit", "-am", "Latest")
        self.latest = git(self.root, "rev-parse", "HEAD")
        git(Path(self.tmp.name), "init", "--bare", str(self.remote))
        git(self.root, "remote", "add", "origin", str(self.remote))
        git(self.root, "push", "origin", "HEAD:refs/heads/downstream/patch-build", "--tags")
        self.published = {"id": 1, "tag_name": "v1.2.3-fork.1",
                          "draft": False, "prerelease": False}
        self.draft = {"id": 2, "tag_name": "v1.2.3-fork.2",
                      "draft": True, "prerelease": False}

    def remote_sha(self, tag):
        return git(self.remote, "rev-parse", "refs/tags/" + tag)

    def launch(self, api, plan=False):
        observed = []
        head = git(self.root, "rev-parse", "HEAD")
        status = git(self.root, "status", "--porcelain", "--untracked-files=all")
        files = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*")
                 if p.is_file() and ".git" not in p.relative_to(self.root).parts}
        try:
            with patch.object(driver, "ROOT", self.root), patch.object(driver, "api", api), \
                 patch.object(driver, "verify_origin"), \
                 patch.object(driver, "watch", side_effect=lambda *args: observed.append(args)), \
                 patch.object(sys, "argv", ["release.py"] + (["--plan"] if plan else [])):
                driver.main()
        finally:
            self.assertEqual(git(self.root, "rev-parse", "HEAD"), head)
            self.assertEqual(git(self.root, "status", "--porcelain", "--untracked-files=all"), status)
            self.assertEqual({p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*")
                              if p.is_file() and ".git" not in p.relative_to(self.root).parts}, files)
            self.assertEqual(git(self.remote, "rev-parse", "refs/heads/downstream/patch-build"), self.latest)
        return observed

    def check_tag_push_failure_retry(self, accepted):
        tag = "v1.2.3-fork.2"
        ref = "refs/tags/" + tag
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()])
        real_git = driver.git
        attempted = []

        def fail_tag_push(*args):
            if args[0] == "push" and args[-1].endswith(":" + ref) and not args[-1].startswith(":"):
                attempted.append(args)
                if accepted:
                    real_git(*args)
                raise subprocess.CalledProcessError(1, ["git", *args])
            return real_git(*args)

        with patch.object(driver, "git", side_effect=fail_tag_push):
            with self.assertRaises(subprocess.CalledProcessError):
                self.launch(api)
        self.assertEqual(len(attempted), 1)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)
        self.assertEqual(git(self.root, "tag", "-l", tag), "")
        remote_tag = git(self.root, "ls-remote", "--refs", "origin", ref)
        self.assertEqual(remote_tag, f"{self.latest}\t{ref}" if accepted else "")

        retry_pushes = []
        def record_pushes(*args):
            if args[0] == "push":
                retry_pushes.append(args)
            return real_git(*args)

        with patch.object(driver, "git", side_effect=record_pushes):
            observed = self.launch(api)
        self.assertEqual([args[-1] for args in retry_pushes],
                         ([":" + ref] if accepted else []) + [self.latest + ":" + ref])
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)
        self.assertEqual(self.remote_sha(tag), self.latest)
        self.assertEqual(git(self.root, "tag", "-l", tag), "")
        self.assertEqual(observed[0][:2], (tag, self.latest))

    def test_tag_push_failure_before_remote_acceptance_retries(self):
        self.check_tag_push_failure_retry(accepted=False)

    def test_tag_push_failure_after_remote_acceptance_retries(self):
        self.check_tag_push_failure_retry(accepted=True)

    def test_draft_and_old_tag_are_replaced_at_original_head(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()], active=True)
        observed = self.launch(api)
        self.assertEqual(self.remote_sha("v1.2.3-fork.1"), self.old)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.latest)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/downstream/patch-build"), self.latest)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)
        self.assertEqual(observed[0][:2], ("v1.2.3-fork.2", self.latest))
        self.assertTrue(any(method == "POST" and path.endswith("/42/cancel") for method, path in api.calls))
        self.assertTrue(any(method == "DELETE" and path.endswith("/releases/2") for method, path in api.calls))

    def test_publication_after_draft_deletion_preserves_tag(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()],
                      publish_on_delete=True)
        with self.assertRaises(RuntimeError):
            self.launch(api)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)

    def test_published_race_during_cancellation_preserves_existing_tag(self):
        api = FakeAPI(self.baseline, [self.published.copy()], active=True, publish_on_cancel=True)
        with self.assertRaises(RuntimeError):
            self.launch(api)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)
        self.assertFalse(any(method == "DELETE" for method, _ in api.calls))

    def test_api_failure_never_removes_candidate_tag(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()],
                      fail="/actions/workflows/")
        with self.assertRaises(subprocess.CalledProcessError):
            self.launch(api)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)
        self.assertFalse(any(method == "DELETE" for method, _ in api.calls))

    def test_plan_is_read_only_and_published_numbers_are_not_reused(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()])
        self.assertEqual(self.launch(api, plan=True), [])
        self.assertEqual(self.remote_sha("v1.2.3-fork.1"), self.old)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)
        self.assertTrue(all(method == "GET" for method, _ in api.calls))
        self.assertEqual(driver.select([self.published, {"tag_name": "v1.2.3-fork.4",
                         "draft": False, "prerelease": False}, self.draft], "1.2.3"),
                         "v1.2.3-fork.5")

    def test_prerelease_number_is_not_reused(self):
        prerelease = {"tag_name": "v1.2.3-fork.7", "draft": False, "prerelease": True}
        self.assertEqual(driver.select([self.published, self.draft, prerelease], "1.2.3"),
                         "v1.2.3-fork.8")


if __name__ == "__main__":
    unittest.main()
