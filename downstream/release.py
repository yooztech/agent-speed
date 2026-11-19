#!/usr/bin/env python3
"""Safely prepare, trigger, and observe the downstream Release workflow."""
from contextlib import contextmanager, nullcontext, redirect_stderr
from datetime import datetime, timezone
import argparse
import fcntl
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unicodedata
from urllib.parse import quote
import release_network

ROOT = Path(__file__).resolve().parent.parent
BRANCH = 'downstream/patch-build'
REPO = 'yooztech/agent-speed'
UPSTREAM = 'zoefix/agent-speed'
GH = os.environ.get('RELEASE_GH', 'gh')
TIMEOUT = 4 * 60 * 60



def command(args, *, capture=True, deadline=None):
    return release_network.run(args, cwd=ROOT, capture=capture, deadline=deadline)


def git(*args, deadline=None):
    if args and args[0] == 'ls-remote':
        return command(['git', *args], deadline=deadline).strip()
    if args and args[0] == 'push':
        return release_network.run_once(['git', *args], cwd=ROOT).strip()
    return subprocess.run(['git', *args], cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


@contextmanager
def committed_snapshot(commit):
    """Export the selected commit without consulting the mutable checkout."""
    with tempfile.TemporaryDirectory(prefix='agent-speed-release-snapshot-') as temp:
        root = Path(temp) / 'checkout'
        root.mkdir()
        archive = Path(temp) / 'commit.tar'
        git('archive', '--format=tar', '--output=' + str(archive), commit)
        with tarfile.open(archive) as source:
            # This archive is produced by Git from our trusted commit, not external input.
            # Python 3.10 installations do not all support extraction filters.
            source.extractall(root)
        yield root


def preflight(root):
    host = platform.system()
    if host not in ('Linux', 'Darwin'):
        raise RuntimeError(f'release preflight does not support host platform {host}')
    print(f'Release preflight on {host}: patch queue preparation only; '
          'builds, tests and packaging remain Release workflow checks.', flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='agent-speed-release-') as temp:
            tree = Path(temp) / 'source'
            subprocess.run([sys.executable, str(root / 'downstream/manage.py'), 'prepare', str(tree)],
                           cwd=root, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f'release preflight failed: {exc}') from exc


def api(path, method='GET', *, deadline=None):
    args = [GH, 'api', '--method', method, '-H', 'Accept: application/vnd.github+json', path]
    output = (command(args, deadline=deadline) if method == 'GET' else
              release_network.run_once(args, cwd=ROOT, deadline=deadline))
    return json.loads(output) if output and output.strip() else None


def pages(path, key=None, *, deadline=None):
    result = []
    page = 1
    while True:
        separator = '&' if '?' in path else '?'
        value = api(f'{path}{separator}per_page=100&page={page}', deadline=deadline)
        batch = value[key] if key else value
        if not isinstance(batch, list):
            raise RuntimeError(f'invalid API response for {path}')
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def releases(*, deadline=None):
    return pages(f'repos/{REPO}/releases', deadline=deadline)


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


def check_baseline(root):
    config = json.loads((root / 'downstream/config.json').read_text())
    tag = f"v{config['upstream_version']}"
    obj = api(f'repos/{UPSTREAM}/git/ref/tags/{quote(tag, safe="")}')['object']
    for _ in range(8):
        if obj['type'] == 'commit':
            break
        if obj['type'] != 'tag':
            raise RuntimeError('upstream tag does not resolve to a commit')
        obj = api(f"repos/{UPSTREAM}/git/tags/{obj['sha']}")['object']
    else:
        raise RuntimeError('upstream tag nesting is too deep')
    if obj['sha'] != config['upstream_commit']:
        raise RuntimeError(f"upstream pinned tag {tag} resolves to {obj['sha']}, but configured pin is "
                           f"{config['upstream_commit']}; no baseline was changed.")
    latest = api(f'repos/{UPSTREAM}/releases/latest')['tag_name']
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', latest):
        raise RuntimeError(f'unsupported upstream latest release tag: {latest}')
    if latest != tag:
        print(f'WARNING: upstream latest release is {latest}; staying on pinned {tag}. '
              'To upgrade, manually migrate the baseline and patch queue before releasing.', file=sys.stderr)
    return config['upstream_version']

def remote_ref(ref, *, deadline=None):
    output = (git('ls-remote', '--refs', 'origin', ref, deadline=deadline) if deadline is not None
              else git('ls-remote', '--refs', 'origin', ref))
    rows = [line.split() for line in output.splitlines() if line]
    if len(rows) > 1 or (rows and rows[0][1] != ref):
        raise RuntimeError(f'ambiguous remote ref {ref}')
    return rows[0][0] if rows else None


def check_remote_contains(commit):
    """The workflow requires the selected commit to remain on the release branch."""
    ref = 'refs/heads/' + BRANCH
    tip = remote_ref(ref)
    if tip == commit:
        return
    if tip is not None:
        # Fetch only into disposable storage: never move caller refs or FETCH_HEAD.
        with tempfile.TemporaryDirectory(prefix='agent-speed-release-ancestry-') as temp:
            subprocess.run(['git', 'init', '--bare', '--quiet', temp], check=True)
            release_network.run(['git', 'fetch', '--quiet', '--no-tags',
                                 git('remote', 'get-url', 'origin'), ref], cwd=temp)
            result = subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'FETCH_HEAD'],
                                    cwd=temp, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                return
            if result.returncode not in (1, 128):
                result.check_returncode()
    raise RuntimeError(f'remote {BRANCH} no longer contains selected commit {commit}')


def runs(tag, *, deadline=None):
    return pages(f'repos/{REPO}/actions/workflows/release.yml/runs?branch={quote(tag, safe="")}&event=push', 'workflow_runs', deadline=deadline)

def cancel_and_wait(tag):
    deadline = time.monotonic() + 600
    while True:
        active = [r for r in runs(tag, deadline=deadline) if r['status'] != 'completed' and r['head_branch'] == tag]
        if not active:
            return
        for run in active:
            attempted = False
            def cancel():
                nonlocal attempted
                if attempted:
                    ensure_unpublished(tag, deadline=deadline)
                    current = api(f"repos/{REPO}/actions/runs/{run['id']}", deadline=deadline)
                    if current['status'] in ('completed', 'cancelled', 'cancelling'):
                        return
                attempted = True
                api(f"repos/{REPO}/actions/runs/{run['id']}/cancel", 'POST', deadline=deadline)
            try:
                release_network.retry(cancel, label=f"cancel run {run['id']}", deadline=deadline)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                if not release_network.is_transient(exc):
                    raise
                ensure_unpublished(tag, deadline=deadline)
                current = api(f"repos/{REPO}/actions/runs/{run['id']}", deadline=deadline)
                if current['status'] not in ('completed', 'cancelled', 'cancelling'):
                    raise
        for run in active:
            while True:
                current = api(f"repos/{REPO}/actions/runs/{run['id']}", deadline=deadline)
                if current['status'] == 'completed':
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('timed out waiting for old release runs to terminate')
                time.sleep(min(5, max(0, deadline - time.monotonic())))
        if time.monotonic() >= deadline:
            raise RuntimeError('timed out cancelling old release runs')


def delete_draft(tag, draft_id, old_tag, version):
    attempted = False
    def delete():
        nonlocal attempted
        fresh = ensure_unpublished(tag)
        if fresh is None:
            if attempted and select(releases(), version) == tag and remote_ref('refs/tags/' + tag) == old_tag:
                return
            raise RuntimeError('candidate draft disappeared before deletion')
        if fresh['id'] != draft_id or select(releases(), version) != tag or remote_ref('refs/tags/' + tag) != old_tag:
            raise RuntimeError('candidate release or tag changed before draft deletion')
        attempted = True
        api(f'repos/{REPO}/releases/{draft_id}', 'DELETE')
    try:
        release_network.retry(delete, label=f'delete draft {draft_id}')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if not release_network.is_transient(exc):
            raise
        if (ensure_unpublished(tag) is not None or select(releases(), version) != tag
                or remote_ref('refs/tags/' + tag) != old_tag):
            raise


def push_tag(tag, expected, desired, commit):
    ref = 'refs/tags/' + tag
    attempted = False
    def push():
        nonlocal attempted
        ensure_unpublished(tag)
        actual = remote_ref(ref)
        check_remote_contains(commit)
        if attempted and actual == desired:
            return
        if actual != expected:
            raise RuntimeError('candidate tag changed before tag push')
        attempted = True
        git('push', f'--force-with-lease={ref}:{expected or ""}', 'origin', f'{desired or ""}:{ref}')
    try:
        release_network.retry(push, label=f'push {ref}')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if not release_network.is_transient(exc):
            raise
        ensure_unpublished(tag)
        check_remote_contains(commit)
        if remote_ref(ref) != desired:
            raise
    if remote_ref(ref) != desired:
        raise RuntimeError('remote tag did not reach the requested state')
    # git push updates only the remote ref. Keep the local candidate tag aligned so
    # retries cannot leave a stale local tag after the remote tag moved.
    if desired is None:
        git('update-ref', '-d', ref)
    else:
        git('update-ref', ref, desired)


def target_release(tag, *, deadline=None):
    found = [r for r in releases(deadline=deadline) if r['tag_name'] == tag]
    if len(found) > 1:
        raise RuntimeError(f'multiple releases for {tag}; refusing to proceed')
    return found[0] if found else None


def ensure_unpublished(tag, *, deadline=None):
    r = target_release(tag, deadline=deadline)
    if r and (not r['draft'] or r.get('published_at')):
        raise RuntimeError(f'{tag} already has a non-draft release; it is immutable')
    return r


def assets_expected(version):
    return {'AgentSpeed-macOS.zip', 'AgentSpeed-Windows-x64.zip', 'AgentSpeed-Windows-arm64.zip',
            'AgentSpeed-Windows-x64-Setup.exe', 'AgentSpeed-Windows-arm64-Setup.exe',
            'AgentSpeed-Linux-x86_64.AppImage', 'AgentSpeed-Linux-aarch64.AppImage',
            f'agent-speed_{version}_amd64.deb', f'agent-speed_{version}_arm64.deb',
            'SHA256SUMS-Linux-x86_64.txt', 'SHA256SUMS-Linux-aarch64.txt', 'SHA256SUMS.txt',
            'agent-speed-collector-linux-x86_64', 'agent-speed-collector-linux-x86_64.sha256',
            'agent-speed-collector-linux-x86_64.json'}


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
    """Render one live row per job on a TTY; log only status changes through a pipe."""
    STATUS_COLORS = {
        'waiting': '\033[36m',
        'running': '\033[33m',
        'success': '\033[32m',
        'failed': '\033[31m',
        'cancelled': '\033[90m',
        'skipped': '\033[90m',
    }
    RESET = '\033[0m'

    def __init__(self, stream=None):
        self.stream = stream if stream is not None else self._terminal()
        self.tty = self.stream is not None and self.stream.isatty()
        self.lines = 0
        self.previous = {}

    @staticmethod
    def _terminal():
        if os.environ.get('RELEASE_PLAIN_PROGRESS'):
            return None
        if sys.stdout.isatty():
            return sys.stdout
        try:
            stream = open('/dev/tty', 'w')
            if stream.isatty():
                return stream
            stream.close()
        except OSError:
            pass
        return None

    @staticmethod
    def _row(job, index):
        status = progress_status(job)
        name = clean_progress_text(job['name'])
        key = job.get('id', (name, index))
        duration = job_duration(job)
        return key, (name, status), name, status, duration

    def update(self, jobs):
        attempts = [job.get('run_attempt') for job in jobs if isinstance(job.get('run_attempt'), int)]
        if attempts:
            latest = max(attempts)
            jobs = [job for job in jobs if job.get('run_attempt', latest) == latest]
        rows = []
        seen = set()
        for index, job in enumerate(jobs):
            key = job.get('id', clean_progress_text(job['name']))
            if key in seen:
                continue
            seen.add(key)
            rows.append(self._row(job, index))
        if self.tty:
            self._render(rows)
        else:
            for key, signature, name, status, duration in rows:
                if self.previous.get(key) != signature:
                    print(f'{name} | {status} | {duration}', flush=True)
        self.previous = {key: signature for key, signature, *_ in rows}

    def _render(self, rows):
        try:
            width = max(1, os.get_terminal_size(self.stream.fileno()).columns - 1)
        except (AttributeError, OSError, ValueError):
            width = max(1, shutil.get_terminal_size((80, 24)).columns - 1)
        if self.lines:
            print(f'\033[{self.lines}A', end='', file=self.stream)
        count = max(self.lines, len(rows))
        for index in range(count):
            if index < len(rows):
                _, _, name, status, duration = rows[index]
                suffix = f' | {status} | {duration}'
                budget = width - len(suffix)
                if len(name) > budget:
                    name = (fit_terminal(name, budget - 1) + '…') if budget > 1 else ''
                line = name + suffix
                color = self.STATUS_COLORS.get(status)
                if color:
                    marker = f' | {status} |'
                    line = line.replace(marker, f' | {color}{status}{self.RESET} |', 1)
            else:
                line = ''
            print('\r\033[2K' + line, file=self.stream)
        if count > len(rows):
            print(f'\033[{count - len(rows)}A', end='', file=self.stream)
        self.lines = len(rows)
        self.stream.flush()


def watch(tag, sha, old_ids, *, resume_id=None, deadline=None):
    deadline = deadline or time.monotonic() + TIMEOUT
    print(f'Waiting for GitHub Actions Release run for {tag}...', flush=True)
    run_id = resume_id
    announced = False
    display = ProgressDisplay()

    def quiet_read(operation):
        while True:
            if time.monotonic() >= deadline:
                raise RuntimeError('timed out refreshing the Release workflow')
            try:
                with redirect_stderr(io.StringIO()):
                    return operation()
            except (json.JSONDecodeError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
            time.sleep(min(10, max(0, deadline - time.monotonic())))

    while time.monotonic() < deadline:
        matching = quiet_read(
            lambda: ([api(f'repos/{REPO}/actions/runs/{resume_id}', deadline=deadline)] if resume_id is not None else
                     [r for r in runs(tag, deadline=deadline)
                      if r['id'] not in old_ids and r['head_branch'] == tag and r['head_sha'] == sha]))
        if len(matching) > 1:
            raise RuntimeError('multiple new release runs found; inspect Actions manually')
        if matching:
            run = matching[0]
            if resume_id is not None:
                validate_run(run, resume_id, tag, sha)
            if run_id is not None and run_id != run['id']:
                raise RuntimeError('release run changed while watching')
            run_id = run['id']
            if not announced:
                print(f"Found Release run {run_id}: {run.get('html_url') or f'https://github.com/{REPO}/actions/runs/{run_id}'}", flush=True)
                announced = True
            jobs = quiet_read(lambda: pages(f'repos/{REPO}/actions/runs/{run_id}/jobs', 'jobs', deadline=deadline))
            display.update(jobs)
            if run['status'] == 'completed':
                if run['conclusion'] != 'success':
                    raise RuntimeError(f"Release run {run_id} ended: {progress_status(run)}")
                r = quiet_read(lambda: target_release(tag, deadline=deadline))
                if not r or r['draft'] or r['prerelease']:
                    raise RuntimeError('workflow succeeded but no formal published release exists')
                if quiet_read(lambda: remote_ref('refs/tags/' + tag, deadline=deadline)) != sha:
                    raise RuntimeError('published tag no longer matches the release commit')
                assets = quiet_read(lambda: pages(f"repos/{REPO}/releases/{r['id']}/assets", deadline=deadline))
                names = {a['name'] for a in assets if a.get('state') == 'uploaded' and a.get('size', 0) > 0}
                missing = assets_expected(tag[1:]) - names
                if missing:
                    raise RuntimeError('published release is missing assets: ' + ', '.join(sorted(missing)))
                print(f'Published {tag} with all expected assets (run {run_id}).')
                return
        else:
            display.update([])
        time.sleep(min(10, max(0, deadline - time.monotonic())))
    raise RuntimeError('timed out watching the Release workflow; inspect Actions before retrying')


def validate_run(run, run_id, tag=None, sha=None):
    actual_tag, actual_sha = run.get('head_branch'), run.get('head_sha')
    if (run.get('id') != run_id or run.get('event') != 'push'
            or run.get('path', '').split('@', 1)[0] != '.github/workflows/release.yml'
            or run.get('repository', {}).get('full_name', '').lower() != REPO.lower()
            or not isinstance(actual_tag, str)
            or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+-fork\.[1-9][0-9]*', actual_tag)
            or not isinstance(actual_sha, str) or not re.fullmatch(r'[0-9a-f]{40}', actual_sha)
            or (tag is not None and actual_tag != tag) or (sha is not None and actual_sha != sha)):
        raise RuntimeError('run is not the requested repository Release tag push')
    return actual_tag, actual_sha


def resume(run_id):
    deadline = time.monotonic() + TIMEOUT
    run = api(f'repos/{REPO}/actions/runs/{run_id}', deadline=deadline)
    tag, sha = validate_run(run, run_id)
    watch(tag, sha, set(), resume_id=run_id, deadline=deadline)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan', action='store_true', help='query and print the next candidate without changing anything')
    mode.add_argument('--resume', type=int, metavar='RUN_ID', help='read-only observation of an existing Release run')
    args = parser.parse_args()
    if args.resume is not None:
        if args.resume <= 0:
            parser.error('RUN_ID must be positive')
        resume(args.resume)
        return
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
        current = git('rev-parse', 'HEAD')
        with committed_snapshot(current) as snapshot:
            verify_origin()
            branch_ref = 'refs/heads/' + BRANCH
            remote = remote_ref(branch_ref)
            if remote != current:
                raise RuntimeError(f'local HEAD {current} is not latest origin/{BRANCH} ({remote}); synchronize safely first')
            version = check_baseline(snapshot)
            rels = releases()
            tag = select(rels, version)
            old_tag = remote_ref('refs/tags/' + tag)
            print(f'Candidate {tag}, branch {current}, existing tag {old_tag or "none"}', flush=True)
            if args.plan:
                return
            preflight(snapshot)
        cancel_and_wait(tag)
        draft = ensure_unpublished(tag)
        if select(releases(), version) != tag:
            raise RuntimeError('published release history changed; retry planning')
        check_remote_contains(current)
        if remote_ref('refs/tags/' + tag) != old_tag:
            raise RuntimeError('candidate tag changed during planning')
        if draft:
            delete_draft(tag, draft['id'], old_tag, version)
        # Recheck after cancellation and draft deletion, before the destructive tag operation.
        ensure_unpublished(tag)
        if old_tag:
            push_tag(tag, old_tag, None, current)
        check_remote_contains(current)
        ensure_unpublished(tag)
        if remote_ref('refs/tags/' + tag) is not None:
            raise RuntimeError('candidate tag appeared concurrently')
        old_ids = {r['id'] for r in runs(tag)}
        push_tag(tag, None, current, current)
        watch(tag, current, old_ids)

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f'release: {exc}', file=sys.stderr)
        if getattr(exc, 'stderr', None):
            print(exc.stderr, file=sys.stderr, end='' if exc.stderr.endswith('\n') else '\n')
        sys.exit(1)
