#!/usr/bin/env python3
"""Safely prepare, trigger, and observe the downstream Release workflow."""
from contextlib import nullcontext
from datetime import datetime, timezone
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
BRANCH = 'downstream/patch-build'
REPO = 'yooztech/agent-speed'
UPSTREAM = 'zoefix/agent-speed'
GH = os.environ.get('RELEASE_GH', 'gh')
TIMEOUT = 4 * 60 * 60



def command(args, *, capture=True):
    return subprocess.run(args, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def git(*args):
    return command(['git', *args]).strip()


def find_dotnet_sdk():
    """Select a .NET 10 installation in explicit, PATH, then user-local order."""
    name = 'dotnet.exe' if os.name == 'nt' else 'dotnet'
    root = os.environ.get('DOTNET_ROOT')
    candidates = ([Path(root) / name] if root else [])
    for directory in os.get_exec_path():
        candidates.append(Path(directory) / name)
    candidates.append(Path.home() / '.dotnet' / name)
    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        env = os.environ.copy()
        env['DOTNET_ROOT'] = str(candidate.parent)
        env['PATH'] = str(candidate.parent) + os.pathsep + env.get('PATH', '')
        try:
            result = subprocess.run([str(candidate), '--list-sdks'], check=True, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        except (OSError, subprocess.CalledProcessError):
            continue
        if re.search(r'^10\.\d+\.\d+\S*\s', result.stdout, re.MULTILINE):
            return str(candidate), env
    raise RuntimeError('.NET 10 SDK is required for release preflight; install it and set DOTNET_ROOT or PATH, or install it in ~/.dotnet')


def preflight():
    host = platform.system()
    if host not in ('Linux', 'Darwin'):
        raise RuntimeError(f'release preflight does not support host platform {host}')
    required = ('cmake', 'ctest') if host == 'Linux' else ('swift',)
    for tool in required:
        if not shutil.which(tool):
            raise RuntimeError(f'{tool} is required for release preflight on {host}')
    print(f'Release preflight on {host}: Windows cross-platform build, Core traffic smoke test and full Presentation tests; '
          + ('Linux headless core build and tests.' if host == 'Linux' else 'native macOS Swift tests.'),
          flush=True)
    print('Native UI tests and platform packaging remain Release workflow checks; '
          'other platforms are not validated locally.', flush=True)
    dotnet, dotnet_env = find_dotnet_sdk()
    try:
        with tempfile.TemporaryDirectory(prefix='agent-speed-release-') as temp:
            tree = Path(temp) / 'source'
            subprocess.run([sys.executable, str(ROOT / 'downstream/manage.py'), 'prepare', str(tree)],
                           cwd=ROOT, check=True)
            subprocess.run([dotnet, 'build', 'windows/AgentSpeed.slnx', '-c', 'Release',
                            '-p:EnableWindowsTargeting=true'], cwd=tree, check=True, env=dotnet_env)
            subprocess.run([dotnet, 'test', 'windows/tests/AgentSpeed.Core.Tests', '-c', 'Release',
                            '-f', 'net10.0', '--no-build', '--filter',
                            'FullyQualifiedName=AgentSpeed.Core.Tests.RemoteConsumerTests.RemoteTrafficIsOptionalAndRetainsCountsAcrossDisconnectAndRestart'],
                           cwd=tree, check=True, env=dotnet_env)
            subprocess.run([dotnet, 'test', 'windows/tests/AgentSpeed.Presentation.Tests', '-c', 'Release',
                            '-f', 'net10.0', '--no-build'], cwd=tree, check=True, env=dotnet_env)
            if host == 'Linux':
                build = Path(temp) / 'linux-build'
                configure = ['cmake', '-S', 'linux', '-B', str(build),
                             '-DAGENTSPEED_BUILD_APP=OFF']
                googletest = Path('/usr/src/googletest')
                if (googletest / 'CMakeLists.txt').is_file():
                    configure.append(f'-DFETCHCONTENT_SOURCE_DIR_GOOGLETEST={googletest}')
                subprocess.run(configure, cwd=tree, check=True)
                subprocess.run(['cmake', '--build', str(build), '--parallel', '2'], cwd=tree, check=True)
                subprocess.run(['ctest', '--test-dir', str(build), '--output-on-failure'], cwd=tree, check=True)
            else:
                subprocess.run(['swift', 'test'], cwd=tree / 'macos', check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f'release preflight failed: {exc}') from exc


def check_checkout(commit):
    if (git('branch', '--show-current') != BRANCH or git('rev-parse', 'HEAD') != commit
            or git('status', '--porcelain', '--untracked-files=all')):
        raise RuntimeError('local branch, HEAD or working tree changed during release')


def api(path, method='GET'):
    args = [GH, 'api', '--method', method, '-H', 'Accept: application/vnd.github+json', path]
    output = command(args)
    return json.loads(output) if output and output.strip() else None


def pages(path, key=None):
    result = []
    page = 1
    while True:
        separator = '&' if '?' in path else '?'
        value = api(f'{path}{separator}per_page=100&page={page}')
        batch = value[key] if key else value
        if not isinstance(batch, list):
            raise RuntimeError(f'invalid API response for {path}')
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def releases():
    return pages(f'repos/{REPO}/releases')


def select(rels, version):
    pattern = re.compile(r'v' + re.escape(version) + r'-fork\.([1-9][0-9]*)\Z')
    published = [int(m.group(1)) for r in rels if not r['draft']
                 if (m := pattern.fullmatch(r['tag_name']))]
    return f'v{version}-fork.{max(published, default=0) + 1}'


def verify_origin():
    expected = re.compile(r'(?i)(?:https://(?:[^/@]+@)?github\.com/|ssh://(?:git@)?github\.com/|git@github\.com:)' + re.escape(REPO) + r'(?:\.git)?/?\Z')
    urls = [git('remote', 'get-url', 'origin'), *git('remote', 'get-url', '--push', '--all', 'origin').splitlines()]
    if not urls or any(not expected.fullmatch(url) for url in urls):
        raise RuntimeError(f'origin fetch and all push URLs must refer to github.com/{REPO}')


def check_baseline():
    config = json.loads((ROOT / 'downstream/config.json').read_text())
    latest = api(f'repos/{UPSTREAM}/releases/latest')
    tag = latest['tag_name']
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise RuntimeError(f'unsupported upstream latest release tag: {tag}')
    obj = api(f'repos/{UPSTREAM}/git/ref/tags/{quote(tag, safe="")}')['object']
    for _ in range(8):
        if obj['type'] == 'commit':
            break
        if obj['type'] != 'tag':
            raise RuntimeError('upstream tag does not resolve to a commit')
        obj = api(f"repos/{UPSTREAM}/git/tags/{obj['sha']}")['object']
    else:
        raise RuntimeError('upstream tag nesting is too deep')
    if tag[1:] != config['upstream_version'] or obj['sha'] != config['upstream_commit']:
        raise RuntimeError(f"upstream latest {tag} resolves to {obj['sha']}, but pin is "
                           f"v{config['upstream_version']} {config['upstream_commit']}. "
                           'Migrate downstream/config.json and replay/rebase the patch queue against the new upstream, '
                           'update its tests and release notes, commit the migration, then retry; no baseline was changed.')
    return tag[1:]


def remote_ref(ref):
    output = git('ls-remote', '--refs', 'origin', ref)
    rows = [line.split() for line in output.splitlines() if line]
    if len(rows) > 1 or (rows and rows[0][1] != ref):
        raise RuntimeError(f'ambiguous remote ref {ref}')
    return rows[0][0] if rows else None


def runs(tag):
    return pages(f'repos/{REPO}/actions/workflows/release.yml/runs?branch={quote(tag, safe="")}&event=push', 'workflow_runs')


def cancel_and_wait(tag):
    deadline = time.monotonic() + 600
    while True:
        active = [r for r in runs(tag) if r['status'] != 'completed' and r['head_branch'] == tag]
        if not active:
            return
        for run in active:
            api(f"repos/{REPO}/actions/runs/{run['id']}/cancel", 'POST')
        for run in active:
            while True:
                current = api(f"repos/{REPO}/actions/runs/{run['id']}")
                if current['status'] == 'completed':
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('timed out waiting for old release runs to terminate')
                time.sleep(5)
        if time.monotonic() >= deadline:
            raise RuntimeError('timed out cancelling old release runs')


def target_release(tag):
    found = [r for r in releases() if r['tag_name'] == tag]
    if len(found) > 1:
        raise RuntimeError(f'multiple releases for {tag}; refusing to proceed')
    return found[0] if found else None


def ensure_unpublished(tag):
    r = target_release(tag)
    if r and (not r['draft'] or r.get('published_at')):
        raise RuntimeError(f'{tag} already has a non-draft release; it is immutable')
    return r


def assets_expected(version):
    return {'AgentSpeed-macOS.zip', 'AgentSpeed-Windows-x64.zip', 'AgentSpeed-Windows-arm64.zip',
            'AgentSpeed-Windows-x64-Setup.exe', 'AgentSpeed-Windows-arm64-Setup.exe',
            'AgentSpeed-Linux-x86_64.AppImage', 'AgentSpeed-Linux-aarch64.AppImage',
            f'agent-speed_{version}_amd64.deb', f'agent-speed_{version}_arm64.deb',
            'SHA256SUMS-Linux-x86_64.txt', 'SHA256SUMS-Linux-aarch64.txt', 'SHA256SUMS.txt'}


def progress_status(item):
    if item['status'] != 'completed':
        return 'running' if item['status'] == 'in_progress' else 'waiting'
    conclusion = item.get('conclusion')
    if conclusion == 'success':
        return 'success'
    if conclusion in ('cancelled', 'skipped'):
        return 'cancelled' if conclusion == 'cancelled' else 'skipped'
    return 'failed'


def job_duration(job):
    try:
        start = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
        end = (datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00'))
               if job.get('completed_at') else datetime.now(timezone.utc))
        seconds = max(0, int((end - start).total_seconds()))
    except (KeyError, TypeError, ValueError):
        return '-'
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:d}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'


def clean_progress_text(text):
    return ' '.join(''.join(c if c.isprintable() else ' ' for c in str(text)).split())


def fit_terminal(text, width):
    result = ''
    used = 0
    for char in text:
        cells = 2 if unicodedata.east_asian_width(char) in ('W', 'F') else (0 if unicodedata.combining(char) else 1)
        if used + cells > width:
            break
        result += char
        used += cells
    return result


class ProgressDisplay:
    """Render a live table on a direct TTY, or a compact change log through tee."""
    def __init__(self):
        self.tty = sys.stdout.isatty()
        self.lines = 0
        self.previous = {}
        self.last_output = time.monotonic()

    def update(self, jobs):
        now = time.monotonic()
        rows = []
        for index, job in enumerate(jobs):
            status = progress_status(job)
            current = next((step for step in job.get('steps', [])
                            if step['status'] == 'in_progress'), None) if status == 'running' else None
            step = clean_progress_text(current['name']) if current else ''
            name = clean_progress_text(job['name'])
            key = job.get('id', (name, index))
            signature = (name, status, step)
            duration = job_duration(job)
            row = f"{name} | {status} | {duration}" + (f' | {step}' if step else '')
            rows.append((key, signature, row, name, status, duration, step))
        if self.tty:
            if self.lines:
                print(f'\033[{self.lines}A', end='')
            width = max(1, shutil.get_terminal_size((80, 24)).columns - 1)
            count = max(self.lines, len(rows))
            for index in range(count):
                if index < len(rows):
                    _, _, _, name, status, duration, step = rows[index]
                    suffix = f' | {status} | {duration}'
                    available = max(0, width - len(suffix))
                    if len(name) > available and available > 3:
                        left = (available - 1) // 2
                        name = name[:left] + '…' + name[-(available - left - 1):]
                    line = name + suffix + (f' | {step}' if step else '')
                    line = fit_terminal(line, width)
                else:
                    line = ''
                print('\r\033[2K' + line)
            if count > len(rows):
                print(f'\033[{count - len(rows)}A', end='')
            self.lines = len(rows)
            sys.stdout.flush()
        else:
            changed = [row for key, signature, row, *_ in rows if self.previous.get(key) != signature]
            for row in changed:
                print(row, flush=True)
            if changed:
                self.last_output = now
            elif now - self.last_output >= 60:
                print(f'Actions still running ({len(rows)} jobs reported).', flush=True)
                self.last_output = now
        self.previous = {key: signature for key, signature, *_ in rows}


def watch(tag, sha, old_ids):
    started = time.monotonic()
    deadline = started + TIMEOUT
    print(f'Waiting for GitHub Actions Release run for {tag}...', flush=True)
    run_id = None
    announced = False
    display = ProgressDisplay()
    while time.monotonic() < deadline:
        matching = [r for r in runs(tag) if r['id'] not in old_ids and r['head_branch'] == tag and r['head_sha'] == sha]
        if len(matching) > 1:
            raise RuntimeError('multiple new release runs found; inspect Actions manually')
        if matching:
            run = matching[0]
            if run_id is not None and run_id != run['id']:
                raise RuntimeError('release run changed while watching')
            run_id = run['id']
            if not announced:
                print(f"Found Release run {run_id}: {run.get('html_url') or f'https://github.com/{REPO}/actions/runs/{run_id}'}", flush=True)
                announced = True
            jobs = pages(f'repos/{REPO}/actions/runs/{run_id}/jobs', 'jobs')
            display.update(jobs)
            if run['status'] == 'completed':
                if run['conclusion'] != 'success':
                    raise RuntimeError(f"Release run {run_id} ended: {progress_status(run)}")
                r = target_release(tag)
                if not r or r['draft'] or r['prerelease']:
                    raise RuntimeError('workflow succeeded but no formal published release exists')
                if remote_ref('refs/tags/' + tag) != sha:
                    raise RuntimeError('published tag no longer matches the release commit')
                assets = pages(f"repos/{REPO}/releases/{r['id']}/assets")
                names = {a['name'] for a in assets if a.get('state') == 'uploaded' and a.get('size', 0) > 0}
                missing = assets_expected(tag[1:]) - names
                if missing:
                    raise RuntimeError('published release is missing assets: ' + ', '.join(sorted(missing)))
                print(f'Published {tag} with all expected assets (run {run_id}).')
                return
        else:
            display.update([])
        time.sleep(10)
    raise RuntimeError('timed out watching the Release workflow; inspect Actions before retrying')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true', help='query and print the next candidate without changing anything')
    args = parser.parse_args()
    common = Path(git('rev-parse', '--git-common-dir'))
    if not common.is_absolute():
        common = ROOT / common
    # Reuse an existing Git file: releasing must not create workspace or lock files.
    lock_context = nullcontext(None) if args.plan else (common / 'config').open('rb')
    with lock_context as lock:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if git('branch', '--show-current') != BRANCH:
            raise RuntimeError(f'checkout {BRANCH} before releasing')
        if git('status', '--porcelain', '--untracked-files=all'):
            raise RuntimeError('working tree must be clean, including untracked files')
        verify_origin()
        version = check_baseline()
        rels = releases()
        tag = select(rels, version)
        current = git('rev-parse', 'HEAD')
        branch_ref = 'refs/heads/' + BRANCH
        remote = remote_ref(branch_ref)
        if remote != current:
            raise RuntimeError(f'local HEAD {current} is not latest origin/{BRANCH} ({remote}); synchronize safely first')
        old_tag = remote_ref('refs/tags/' + tag)
        local_tag = git('tag', '-l', tag)
        if local_tag and (old_tag is None or git('rev-parse', f'refs/tags/{tag}') != old_tag):
            raise RuntimeError('local candidate tag differs from remote tag; resolve it manually')
        print(f'Candidate {tag}, branch {current}, existing tag {old_tag or "none"}', flush=True)
        if args.plan:
            return
        preflight()
        cancel_and_wait(tag)
        check_checkout(current)
        draft = ensure_unpublished(tag)
        if select(releases(), version) != tag:
            raise RuntimeError('published release history changed; retry planning')
        if remote_ref(branch_ref) != current or remote_ref('refs/tags/' + tag) != old_tag:
            raise RuntimeError('branch or candidate tag changed during planning')
        if draft:
            fresh = ensure_unpublished(tag)
            if not fresh or fresh['id'] != draft['id']:
                raise RuntimeError('candidate draft changed before deletion')
            if select(releases(), version) != tag or remote_ref('refs/tags/' + tag) != old_tag:
                raise RuntimeError('candidate release or tag changed before draft deletion')
            fresh = ensure_unpublished(tag)
            if not fresh or fresh['id'] != draft['id']:
                raise RuntimeError('candidate draft changed before deletion')
            api(f"repos/{REPO}/releases/{draft['id']}", 'DELETE')
        # Recheck after cancellation and draft deletion, before the destructive tag operation.
        ensure_unpublished(tag)
        if old_tag:
            git('push', f'--force-with-lease=refs/tags/{tag}:{old_tag}', 'origin', f':refs/tags/{tag}')
        if local_tag:
            git('tag', '-d', tag)
        if remote_ref(branch_ref) != current:
            raise RuntimeError('remote branch changed before tagging')
        ensure_unpublished(tag)
        if remote_ref('refs/tags/' + tag) is not None:
            raise RuntimeError('candidate tag appeared concurrently')
        old_ids = {r['id'] for r in runs(tag)}
        check_checkout(current)
        if remote_ref(branch_ref) != current:
            raise RuntimeError('remote branch changed before tagging')
        git('push', f'--force-with-lease=refs/tags/{tag}:', 'origin', f'{current}:refs/tags/{tag}')
        watch(tag, current, old_ids)

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f'release: {exc}', file=sys.stderr)
        sys.exit(1)
