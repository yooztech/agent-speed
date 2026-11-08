#!/usr/bin/env python3
"""Exercise release selection and race safeguards with local Git remotes."""
from contextlib import nullcontext, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("release_driver", HERE / "release.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
installer_spec = importlib.util.spec_from_file_location(
    "installer_version", HERE / "verify-windows-installer-version.py")
installer_version = importlib.util.module_from_spec(installer_spec)
installer_spec.loader.exec_module(installer_version)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


class CollectorAssetContractTests(unittest.TestCase):
    def test_standalone_assets_are_required(self):
        assets = driver.assets_expected('1.2.3-fork.1')
        name = 'agent-speed-collector-linux-x86_64'
        self.assertTrue({name, name + '.sha256', name + '.json'} <= assets)


class FakeAPI:
    def __init__(self, baseline, releases, active=False, publish_on_cancel=False,
                 publish_on_delete=False, fail=None, latest_tag="v1.2.3", annotated=False):
        self.baseline = baseline
        self.latest_tag = latest_tag
        self.annotated = annotated
        self.releases = releases
        self.active = active
        self.publish_on_cancel = publish_on_cancel
        self.publish_on_delete = publish_on_delete
        self.fail = fail
        self.calls = []

    def __call__(self, path, method="GET", *, deadline=None):
        self.calls.append((method, path))
        if self.fail and self.fail in path:
            raise subprocess.CalledProcessError(1, ["gh", "api", path])
        if path.endswith("/releases/latest"):
            return {"tag_name": self.latest_tag}
        if "/git/ref/tags/" in path:
            if not path.endswith("/v1.2.3"):
                raise AssertionError(f"unexpected upstream tag: {path}")
            return {"object": {"type": "tag" if self.annotated else "commit",
                               "sha": "tag-object" if self.annotated else self.baseline}}
        if path.endswith("/git/tags/tag-object") and self.annotated:
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


class DotnetDiscoveryTests(unittest.TestCase):
    def test_precedence_fallback_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            explicit, first, second, local = (home / name for name in ('explicit', 'first', 'second', '.dotnet'))
            for directory in (explicit, first, second, local):
                directory.mkdir()
                executable = directory / 'dotnet'
                executable.write_text(f'#!{sys.executable}\nimport os\n'
                                      'assert os.environ["DOTNET_ROOT"] == os.path.dirname(__file__)\n'
                                      'assert os.environ["PATH"].split(os.pathsep)[0] == os.path.dirname(__file__)\n'
                                      'print("10.0.403 [/sdk]")\n')
                executable.chmod(0o755)
            env = {'HOME': tmp, 'DOTNET_ROOT': str(explicit), 'PATH': os.pathsep.join((str(first), str(second)))}
            with patch.dict(os.environ, env, clear=True):
                chosen, child_env = driver.find_dotnet_sdk()
                self.assertEqual(chosen, str(explicit / 'dotnet'))
                self.assertEqual(child_env['DOTNET_ROOT'], str(explicit))
                self.assertEqual(child_env['PATH'].split(os.pathsep)[0], str(explicit))
                (explicit / 'dotnet').write_text(f'#!{sys.executable}\nprint("7.0.109 [/sdk]")\n')
                self.assertEqual(driver.find_dotnet_sdk()[0], str(first / 'dotnet'))
                (first / 'dotnet').unlink()
                self.assertEqual(driver.find_dotnet_sdk()[0], str(second / 'dotnet'))
                (second / 'dotnet').unlink()
                self.assertEqual(driver.find_dotnet_sdk()[0], str(local / 'dotnet'))
                (local / 'dotnet').unlink()
                with self.assertRaisesRegex(RuntimeError, r'\.NET 10 SDK is required'):
                    driver.find_dotnet_sdk()


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
        (self.root / "downstream/manage.py").write_text(textwrap.dedent('''\
            import os, pathlib, sys
            assert sys.argv[1] == "prepare"
            tree = pathlib.Path(sys.argv[2])
            assert not tree.exists()
            with open(os.environ["PREFLIGHT_LOG"], "a") as log:
                log.write("prepare " + str(tree) + "\\n")
            if os.environ.get("PREFLIGHT_FAIL") == "prepare":
                sys.exit(1)
            for directory in ("windows", "linux", "macos"):
                (tree / directory).mkdir(parents=True)
            (tree / "windows/AgentSpeed.slnx").write_text("fixture")
        '''))
        self.sdk = Path(self.tmp.name) / "sdk"
        self.sdk.mkdir()
        dotnet = self.sdk / "dotnet"
        dotnet.write_text(f'#!{sys.executable}\n' + textwrap.dedent('''\
            import os, pathlib, sys
            assert os.environ["DOTNET_ROOT"] == str(pathlib.Path(__file__).resolve().parent)
            assert os.environ["PATH"].split(os.pathsep)[0] == os.environ["DOTNET_ROOT"]
            with open(os.environ["PREFLIGHT_LOG"], "a") as log:
                log.write("dotnet " + " ".join(sys.argv[1:]) + " cwd=" + os.getcwd() + "\\n")
            if sys.argv[1:] == ["--list-sdks"]:
                print("10.0.100 [/sdk]")
            elif sys.argv[1] == "restore":
                assert sys.argv[1:] == ["restore", "windows/AgentSpeed.slnx", "-p:EnableWindowsTargeting=true"]
                assert os.environ["NUGET_ENHANCED_MAX_NETWORK_TRY_COUNT"] == "6"
            elif sys.argv[1] == "build":
                assert sys.argv[1:] == ["build", "windows/AgentSpeed.slnx", "-c", "Release", "--no-restore", "-p:EnableWindowsTargeting=true"]
                assert pathlib.Path("windows/AgentSpeed.slnx").is_file()
                if os.environ.get("PREFLIGHT_FAIL") == "build":
                    sys.exit(1)
            else:
                assert sys.argv[1] == "test"
                assert sys.argv[2] in ("windows/tests/AgentSpeed.Core.Tests", "windows/tests/AgentSpeed.Presentation.Tests")
                assert sys.argv[3:8] == ["-c", "Release", "-f", "net10.0", "--no-build"]
                if sys.argv[2].endswith("AgentSpeed.Core.Tests"):
                    assert sys.argv[8:] == ["--filter", "FullyQualifiedName=AgentSpeed.Core.Tests.RemoteConsumerTests.RemoteTrafficIsOptionalAndRetainsCountsAcrossDisconnectAndRestart"]
                else:
                    assert sys.argv[8:] == ["--", "xUnit.ParallelizeTestCollections=false"]
                if os.environ.get("PREFLIGHT_FAIL") == pathlib.Path(sys.argv[2]).name:
                    sys.exit(1)
        '''))
        dotnet.chmod(0o755)
        for tool in ("cmake", "ctest", "swift"):
            executable = self.sdk / tool
            executable.write_text(f'#!{sys.executable}\n' + textwrap.dedent('''\
                import os, sys
                tool = os.path.basename(sys.argv[0])
                with open(os.environ["PREFLIGHT_LOG"], "a") as log:
                    log.write(tool + " " + " ".join(sys.argv[1:]) + " cwd=" + os.getcwd() + "\\n")
                stage = tool + ("-build" if sys.argv[1:2] == ["--build"] else "")
                if os.environ.get("PREFLIGHT_FAIL") == stage:
                    sys.exit(1)
            '''))
            executable.chmod(0o755)
        self.preflight_log = Path(self.tmp.name) / "preflight.log"
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

    def launch(self, api, plan=False, fail=None, missing_sdk=False, host="Linux"):
        observed = []
        head = git(self.root, "rev-parse", "HEAD")
        status = git(self.root, "status", "--porcelain", "--untracked-files=all")
        files = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*")
                 if p.is_file() and ".git" not in p.relative_to(self.root).parts}
        env = {"DOTNET_ROOT": str(self.sdk if not missing_sdk else self.sdk / "missing"),
               "PATH": str(self.sdk) + os.pathsep + os.environ.get("PATH", ""),
               "PREFLIGHT_LOG": str(self.preflight_log), "PREFLIGHT_FAIL": fail or ""}
        try:
            with patch.dict(os.environ, env), patch.object(driver, "ROOT", self.root), patch.object(driver, "api", api), \
                 patch.object(driver, "verify_origin"), patch.object(driver.platform, "system", return_value=host), \
                 (patch.object(driver, 'find_dotnet_sdk', side_effect=RuntimeError('.NET 10 SDK is required')) if missing_sdk else nullcontext()):
                with patch.object(driver, "watch", side_effect=lambda *args: observed.append(args)), \
                     patch.object(sys, "argv", ["release.py"] + (["--plan"] if plan else [])):
                    driver.main()
        finally:
            self.assertEqual(git(self.root, "rev-parse", "HEAD"), head)
            self.assertEqual(git(self.root, "status", "--porcelain", "--untracked-files=all"), status)
            self.assertEqual({p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*")
                              if p.is_file() and ".git" not in p.relative_to(self.root).parts}, files)
            self.assertEqual(git(self.remote, "rev-parse", "refs/heads/downstream/patch-build"), self.latest)
        return observed

    def test_newer_upstream_warns_and_releases_pinned_candidate(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()],
                      latest_tag="v1.2.4")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.launch(api)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.latest)
        self.assertIn("WARNING", stderr.getvalue())
        self.assertIn("v1.2.4", stderr.getvalue())
        self.assertIn("pinned v1.2.3", stderr.getvalue())
        self.assertIn("manually migrate", stderr.getvalue())
        config = json.loads((self.root / "downstream/config.json").read_text())
        self.assertEqual(config["upstream_version"], "1.2.3")
        self.assertEqual(config["upstream_commit"], self.baseline)

    def test_retagged_pin_blocks_before_mutation(self):
        api = FakeAPI("b" * 40, [self.published.copy(), self.draft.copy()],
                      latest_tag="v1.2.4")
        with self.assertRaisesRegex(RuntimeError, "pinned tag v1.2.3"):
            self.launch(api)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
        self.assertFalse(self.preflight_log.exists())
        self.assertFalse(any(method != "GET" for method, _ in api.calls))

    def test_annotated_pinned_tag_is_peeled_for_candidate(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()],
                      annotated=True)
        self.launch(api)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.latest)
        self.assertTrue(any(path.endswith("/git/tags/tag-object") for _, path in api.calls))

    def test_accepted_transient_push_is_not_repeated(self):
        tag = 'v1.2.3-fork.2'
        ref = 'refs/tags/' + tag
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()])
        real_git = driver.git
        pushes = []
        def ambiguous(*args, **kwargs):
            if args[0] == 'push' and args[-1] == self.latest + ':' + ref:
                pushes.append(args)
                if len(pushes) == 4:
                    real_git(*args, **kwargs)
                raise subprocess.CalledProcessError(1, args, stderr='connection reset by peer')
            return real_git(*args, **kwargs)
        with patch.object(driver, 'git', side_effect=ambiguous), patch.object(driver.release_network.time, 'sleep'):
            self.launch(api)
        self.assertEqual(len(pushes), 4)
        self.assertEqual(self.remote_sha(tag), self.latest)

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

    def test_preflight_failures_preserve_candidate_and_remote_state(self):
        for host, failure in (("Linux", "prepare"), ("Linux", "build"),
                              ("Linux", "missing_sdk"),
                              ("Linux", "AgentSpeed.Core.Tests"),
                              ("Linux", "AgentSpeed.Presentation.Tests"),
                              ("Linux", "cmake"), ("Linux", "cmake-build"),
                              ("Linux", "ctest"), ("Darwin", "swift")):
            with self.subTest(host=host, failure=failure):
                self.preflight_log.unlink(missing_ok=True)
                api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()], active=True)
                with self.assertRaisesRegex(RuntimeError, "preflight|.NET 10 SDK"):
                    self.launch(api, fail=failure, missing_sdk=failure == "missing_sdk", host=host)
                self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
                self.assertEqual(git(self.root, "rev-parse", "refs/tags/v1.2.3-fork.2"), self.old)
                self.assertTrue(all(method == "GET" for method, _ in api.calls))
                self.assertEqual(len(api.releases), 2)
                if self.preflight_log.exists():
                    for line in self.preflight_log.read_text().splitlines():
                        if line.startswith("prepare "):
                            self.assertFalse(Path(line[8:]).exists())

    def test_preflight_runs_host_commands_in_one_prepared_tree(self):
        for host in ("Linux", "Darwin"):
            with self.subTest(host=host):
                self.preflight_log.unlink(missing_ok=True)
                env = {"DOTNET_ROOT": str(self.sdk / "missing"),
                       "PATH": str(self.sdk) + os.pathsep + os.environ.get("PATH", ""),
                       "PREFLIGHT_LOG": str(self.preflight_log), "PREFLIGHT_FAIL": ""}
                with patch.dict(os.environ, env), patch.object(driver, "ROOT", self.root), \
                     patch.object(driver.platform, "system", return_value=host):
                    driver.preflight()
                lines = self.preflight_log.read_text().splitlines()
                prepares = [line for line in lines if line.startswith("prepare ")]
                self.assertEqual(len(prepares), 1)
                tree = Path(prepares[0][8:])
                self.assertFalse(tree.exists())
                commands = [line for line in lines if not line.startswith("prepare ")]
                self.assertEqual(sum(line.startswith("dotnet build ") for line in commands), 1)
                tests = [line for line in commands if line.startswith("dotnet test ")]
                self.assertEqual(len(tests), 2)
                core_filter = "FullyQualifiedName=AgentSpeed.Core.Tests.RemoteConsumerTests.RemoteTrafficIsOptionalAndRetainsCountsAcrossDisconnectAndRestart"
                self.assertIn(f"dotnet test windows/tests/AgentSpeed.Core.Tests -c Release -f net10.0 --no-build --filter {core_filter} cwd={tree}", tests)
                self.assertTrue(all(f"cwd={tree}" in line for line in commands
                                    if line.startswith(("dotnet build ", "dotnet test "))))
                cmake = [line for line in commands if line.startswith("cmake ")]
                ctest = [line for line in commands if line.startswith("ctest ")]
                swift = [line for line in commands if line.startswith("swift ")]
                if host == "Linux":
                    self.assertEqual(len(cmake), 2)
                    self.assertTrue(cmake[0].startswith("cmake -S linux -B "))
                    self.assertIn("-DAGENTSPEED_BUILD_APP=OFF", cmake[0])
                    build = cmake[0].split(" -B ", 1)[1].split()[0]
                    self.assertEqual(cmake[1], f"cmake --build {build} --parallel 2 cwd={tree}")
                    self.assertEqual(ctest, [f"ctest --test-dir {build} --output-on-failure cwd={tree}"])
                    self.assertEqual(swift, [])
                elif host == "Darwin":
                    self.assertEqual(swift, [f"swift test cwd={tree / 'macos'}"])
                    self.assertEqual(cmake, [])
                    self.assertEqual(ctest, [])

    def test_unknown_host_fails_without_remote_mutation(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()], active=True)
        with self.assertRaises(RuntimeError):
            self.launch(api, host="Windows")
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
        self.assertEqual(git(self.root, "rev-parse", "refs/tags/v1.2.3-fork.2"), self.old)
        self.assertTrue(all(method == "GET" for method, _ in api.calls))
        self.assertEqual(len(api.releases), 2)

    def test_preflight_finishes_and_cleans_up_before_remote_mutations(self):
        api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()], active=True)
        def checked_api(path, method="GET", *, deadline=None):
            if method != "GET":
                lines = self.preflight_log.read_text().splitlines()
                self.assertTrue(any(line.startswith("dotnet build ") for line in lines))
                tree = Path(next(line[8:] for line in lines if line.startswith("prepare ")))
                self.assertFalse(tree.exists())
                self.assertTrue(any("cwd=" + str(tree) in line for line in lines))
            return api(path, method, deadline=deadline)
        self.launch(checked_api)
        self.assertTrue(any(method == "POST" for method, _ in api.calls))
        self.assertTrue(any(method == "DELETE" for method, _ in api.calls))

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
        self.assertFalse(self.preflight_log.exists())
        self.assertEqual(self.remote_sha("v1.2.3-fork.1"), self.old)
        self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.latest)
        self.assertTrue(all(method == "GET" for method, _ in api.calls))
        self.assertEqual(driver.select([self.published, {"tag_name": "v1.2.3-fork.4",
                         "draft": False, "prerelease": False}, self.draft], "1.2.3"),
                         "v1.2.3-fork.5")

    def test_plan_skips_preflight_on_every_host(self):
        for host in ("Linux", "Darwin", "Windows"):
            with self.subTest(host=host):
                api = FakeAPI(self.baseline, [self.published.copy(), self.draft.copy()])
                with patch.object(driver, "preflight") as preflight:
                    self.assertEqual(self.launch(api, plan=True, host=host), [])
                preflight.assert_not_called()
                self.assertTrue(all(method == "GET" for method, _ in api.calls))
                self.assertEqual(self.remote_sha("v1.2.3-fork.2"), self.old)

    def test_prerelease_number_is_not_reused(self):
        prerelease = {"tag_name": "v1.2.3-fork.7", "draft": False, "prerelease": True}
        self.assertEqual(driver.select([self.published, self.draft, prerelease], "1.2.3"),
                         "v1.2.3-fork.8")


class ActionsProgressTests(unittest.TestCase):
    def test_display_transitions_heartbeat_and_matrix(self):
        clock = [0]
        out = io.StringIO()
        jobs = [
            {'id': 1, 'name': 'Build (linux, x86_64)', 'status': 'queued'},
            {'id': 2, 'name': 'Build (linux, arm64)', 'status': 'in_progress',
             'started_at': '2024-01-01T00:00:00Z', 'completed_at': '2024-01-01T01:02:03Z',
             'steps': [{'name': 'Compile', 'status': 'in_progress'}]},
        ]
        with patch.object(sys, 'stdout', out), patch.object(driver.time, 'monotonic', lambda: clock[0]):
            display = driver.ProgressDisplay()
            display.update(jobs)
            clock[0] = 10
            display.update(jobs)
            jobs[0]['status'] = 'in_progress'
            jobs[0]['steps'] = [{'name': 'Test', 'status': 'in_progress'}]
            display.update(jobs)
            clock[0] = 70
            display.update(jobs)
            jobs[0].update(status='completed', conclusion='success', steps=[{'name': 'Complete job', 'status': 'completed'}])
            jobs[1].update(status='completed', conclusion='cancelled')
            display.update(jobs)
        text = out.getvalue()
        self.assertEqual(text.count('Build (linux, x86_64) | waiting'), 1)
        self.assertEqual(text.count('Build (linux, arm64) | running'), 1)
        self.assertIn('Build (linux, arm64) | running | 1:02:03 | Compile', text)
        self.assertIn('Build (linux, x86_64) | running | - | Test', text)
        self.assertIn('Build (linux, x86_64) | success | -', text)
        self.assertIn('Build (linux, arm64) | cancelled | 1:02:03', text)
        self.assertEqual(text.count('Actions still running'), 1)
        self.assertNotIn('Complete job', text)
        self.assertNotIn('\x1b', text)

    def run_watch(self, scenario, cli=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.git').mkdir()
            (root / '.git/config').write_text('')
            fake = root / 'gh'
            fake.write_text(f'#!{sys.executable}\n' + textwrap.dedent('''\
                import json, os, pathlib, sys
                path = sys.argv[-1]
                state = pathlib.Path(os.environ['FAKE_STATE'])
                n = int(state.read_text()) if state.exists() else 0
                if '/workflows/' in path:
                    state.write_text(str(n + 1))
                    if os.environ['SCENARIO'] == 'api-error':
                        print('GitHub API unavailable', file=sys.stderr)
                        sys.exit(7)
                    if n < 2 or os.environ['SCENARIO'] == 'timeout':
                        data = {'workflow_runs': []}
                    else:
                        status = 'completed' if n >= 5 else 'in_progress'
                        conclusion = ('failure' if os.environ['SCENARIO'] == 'failure' else 'success') if status == 'completed' else None
                        data = {'workflow_runs': [{'id': 42, 'head_branch': 'v1.2.3-fork.2', 'head_sha': 'abc', 'status': status, 'conclusion': conclusion, 'html_url': 'https://example.invalid/runs/42'}]}
                elif '/jobs?' in path:
                    status = 'completed' if n >= 6 else 'in_progress'
                    conclusion = ('failure' if os.environ['SCENARIO'] == 'failure' else 'success') if status == 'completed' else None
                    step = 'Package' if n >= 5 else 'Build'
                    data = {'jobs': [{'name': 'Linux', 'status': status, 'conclusion': conclusion, 'steps': [{'name': step, 'status': status, 'conclusion': conclusion}]}, {'name': 'Windows', 'status': 'queued', 'conclusion': None, 'steps': []}, {'name': 'macOS', 'status': 'completed', 'conclusion': 'success', 'steps': [{'name': 'Test', 'status': 'completed', 'conclusion': 'success'}]}]}
                elif '/assets?' in path:
                    data = [{'name': name, 'state': 'uploaded', 'size': 1} for name in json.loads(os.environ['ASSETS'])]
                else:
                    raise AssertionError(path)
                print(json.dumps(data))
            '''))
            fake.chmod(0o755)
            code = textwrap.dedent('''\
                import importlib.util, pathlib, subprocess, sys
                sys.path.insert(0, str(pathlib.Path(sys.argv[1]).parent))
                spec = importlib.util.spec_from_file_location('release', sys.argv[1])
                driver = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(driver)
                clock = [0]
                from types import SimpleNamespace
                driver.time = SimpleNamespace(monotonic=lambda: clock[0],
                    sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
                driver.release_network.time = driver.time
                driver.TIMEOUT = 40 if sys.argv[2] == 'timeout' else 100
                driver.target_release = lambda tag, **kwargs: {'id': 9, 'draft': False, 'prerelease': False}
                driver.remote_ref = lambda ref, **kwargs: 'abc'
                try:
                    if sys.argv[3] == 'cli':
                        driver.ROOT = pathlib.Path(sys.argv[4])
                        pushed = [False]
                        def fake_git(*args):
                            if args == ('rev-parse', '--git-common-dir'): return '.git'
                            if args == ('branch', '--show-current'): return driver.BRANCH
                            if args == ('rev-parse', 'HEAD'): return 'abc'
                            if args[0] == 'push': pushed[0] = True
                            return ''
                        driver.git = fake_git
                        driver.verify_origin = lambda: None
                        driver.check_baseline = lambda: '1.2.3'
                        driver.releases = lambda **kwargs: [{'tag_name': 'v1.2.3-fork.1', 'draft': False}]
                        driver.preflight = lambda: None
                        driver.check_checkout = lambda sha: None
                        driver.ensure_unpublished = lambda tag, **kwargs: None
                        driver.remote_ref = lambda ref, **kwargs: 'abc' if ref.startswith('refs/heads/') or pushed[0] else None
                        sys.argv = ['release.py']
                        driver.main()
                    else:
                        driver.watch('v1.2.3-fork.2', 'abc', set())
                except (RuntimeError, subprocess.CalledProcessError) as exc:
                    print('Release failed:', exc, file=sys.stderr)
                    if getattr(exc, 'stderr', None): print(exc.stderr, file=sys.stderr)
                    sys.exit(1)
            ''')
            env = dict(os.environ, RELEASE_GH=str(fake), FAKE_STATE=str(root / 'state'),
                       SCENARIO=scenario, ASSETS=json.dumps(list(driver.assets_expected('1.2.3-fork.2'))))
            return subprocess.run([sys.executable, '-c', code, str(HERE / 'release.py'), scenario,
                                   'cli' if cli else 'watch', str(root)],
                                  cwd=HERE.parent, env=env, capture_output=True, text=True)

    def test_progress_and_success_in_redirected_output(self):
        result = self.run_watch('success')
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ('Waiting for GitHub Actions', 'https://example.invalid/runs/42',
                     'Linux | running | - | Build', 'Linux | running | - | Package',
                     'Windows | waiting | -', 'macOS | success | -',
                     'Linux | success | -', 'Published v1.2.3-fork.2'):
            self.assertIn(text, result.stdout)
        self.assertNotIn('\x1b', result.stdout)

    def test_failure_timeout_and_api_error_exit_nonzero(self):
        for scenario, message in (('failure', 'ended: failed'),
                                  ('timeout', 'timed out watching'),
                                  ('api-error', 'GitHub API unavailable')):
            with self.subTest(scenario=scenario):
                result = self.run_watch(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn('Published ', result.stdout)
                if scenario == 'failure':
                    self.assertIn('Linux | failed | -', result.stdout)

    def test_release_entrypoint_reports_progress(self):
        result = self.run_watch('success', cli=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Waiting for GitHub Actions Release run', result.stdout)
        self.assertIn('Found Release run 42:', result.stdout)
        self.assertIn('Linux | running | - | Build', result.stdout)
        self.assertIn('Published v1.2.3-fork.2', result.stdout)




class WindowsInstallerVersionTests(unittest.TestCase):
    def test_matching_inno_padding(self):
        for actual in ("1.6.1-fork.3", "1.6.1-fork.3" + " " * 38):
            with self.subTest(actual=actual):
                self.assertTrue(installer_version.matches("1.6.1-fork.3", actual))

    def test_rejects_mismatch_metadata_and_malformed_values(self):
        for actual in ("1.6.1-fork.4", "1.6.1-fork.3+abc", " 1.6.1-fork.3",
                       "1.6.1-fork.3\t", "1.6.1-fork.3 x", "", "1.6.1-fork.3\n"):
            with self.subTest(actual=actual):
                self.assertFalse(installer_version.matches("1.6.1-fork.3", actual))
        for expected in ("", "v1.6.1-fork.3", "1.6.1-fork.3+abc", "1.6.1-fork.3 "):
            with self.subTest(expected=expected):
                self.assertFalse(installer_version.matches(expected, expected))


class NetworkRetryTests(unittest.TestCase):
    def test_classification_and_bounded_backoff(self):
        net = driver.release_network
        for message in ('connection reset by peer', 'HTTP 429', 'HTTP 503', 'HTTP 403: API rate limit exceeded', 'temporary failure in name resolution'):
            self.assertTrue(net.is_transient(subprocess.CalledProcessError(1, ['gh'], stderr=message)), message)
        for message in ('HTTP 401', 'HTTP 403: permission denied', 'HTTP 404', 'validation failed'):
            self.assertFalse(net.is_transient(subprocess.CalledProcessError(1, ['gh'], stderr=message)), message)
        calls = []
        def fail():
            calls.append(1)
            raise subprocess.CalledProcessError(1, ['gh'], stderr='HTTP 503')
        with patch.object(net.time, 'sleep') as sleep:
            with self.assertRaises(subprocess.CalledProcessError):
                net.retry(fail, label='test')
        self.assertEqual(len(calls), 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2, 4])
        with patch.object(net.time, 'monotonic', return_value=10), patch.object(net.time, 'sleep') as sleep:
            with self.assertRaises(TimeoutError):
                net.retry(fail, label='test', deadline=11)
            sleep.assert_not_called()

    def test_resume_is_read_only_and_checks_assets(self):
        tag, sha = 'v1.2.3-fork.2', 'a' * 40
        run = {'id': 42, 'event': 'push', 'path': '.github/workflows/release.yml',
               'repository': {'full_name': driver.REPO}, 'head_branch': tag, 'head_sha': sha,
               'status': 'completed', 'conclusion': 'success'}
        calls = []
        def fake_api(path, method='GET', *, deadline=None):
            calls.append((method, path))
            if path.endswith('/actions/runs/42'):
                return run
            if '/jobs?' in path:
                return {'jobs': []}
            if '/releases?' in path:
                return [{'id': 7, 'tag_name': tag, 'draft': False, 'prerelease': False}]
            if '/assets?' in path:
                return [{'name': name, 'state': 'uploaded', 'size': 1} for name in driver.assets_expected(tag[1:])]
            raise AssertionError(path)
        with patch.object(driver, 'api', side_effect=fake_api), patch.object(driver, 'remote_ref', return_value=sha), \
             patch.object(driver, 'preflight', side_effect=AssertionError('mutation')), \
             patch.object(driver, 'git', side_effect=AssertionError('checkout access')), \
             patch.object(sys, 'argv', ['release.py', '--resume', '42']):
            driver.main()
        self.assertTrue(calls)
        self.assertTrue(all(method == 'GET' for method, _ in calls))
        with self.assertRaises(RuntimeError):
            driver.validate_run({**run, 'event': 'workflow_dispatch'}, 42)


if __name__ == "__main__":
    unittest.main()
