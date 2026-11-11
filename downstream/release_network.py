#!/usr/bin/env python3
"""Bounded retries for transient failures of read-only network operations."""
import re
import subprocess
import sys
import time

_TRANSIENT = re.compile(
    r'connection (?:reset|refused|timed out|aborted)|could not resolve host|'
    r'(?:unexpected|early) EOF|EOF occurred in violation of protocol|'
    r'temporary failure (?:in name resolution|resolving)|name or service not known|'
    r'network (?:is unreachable|error)|timed? out|timeout|'
    r'HTTP[/ ](?:408|429|500|502|503|504)\b|'
    r'\b(?:408|429|500|502|503|504)\b[^\n]*(?:HTTP|response|status)|'
    r'HTTP[/ ]403\b[^\n]*(?:rate limit|secondary rate)|'
    r'(?:rate limit|secondary rate)[^\n]*HTTP[/ ]403\b', re.I)


def is_transient(exc):
    if isinstance(exc, subprocess.TimeoutExpired):
        return True
    if not isinstance(exc, subprocess.CalledProcessError):
        return False
    stderr = exc.stderr or ''
    stdout = exc.stdout or ''
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors='replace')
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors='replace')
    return bool(_TRANSIENT.search(stderr + '\n' + stdout))


def run_once(args, *, cwd=None, capture=True, timeout=60, deadline=None, env=None):
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('network operation deadline exceeded')
        timeout = min(timeout, remaining)
    try:
        result = subprocess.run(args, cwd=cwd, check=True, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, env=env)
    except subprocess.CalledProcessError as exc:
        if not capture and exc.stdout:
            print(exc.stdout, end='', flush=True)
        raise
    if not capture:
        if result.stdout:
            print(result.stdout, end='', flush=True)
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr, flush=True)
        return ''
    return result.stdout


def retry(operation, *, label, deadline=None, attempts=4):
    for attempt in range(attempts):
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(f'{label}: deadline exceeded')
        try:
            return operation()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            if not is_transient(exc) or attempt + 1 >= attempts:
                raise
            delay = 2 ** attempt
            if deadline is not None and time.monotonic() + delay >= deadline:
                raise TimeoutError(f'{label}: deadline exceeded') from exc
            print(f'{label}: transient failure; retrying in {delay}s', file=sys.stderr, flush=True)
            time.sleep(delay)
    raise ValueError('attempts must be positive')


def run(args, *, cwd=None, capture=True, timeout=60, deadline=None, env=None):
    return retry(lambda: run_once(args, cwd=cwd, capture=capture, timeout=timeout,
                                  deadline=deadline, env=env),
                 label=' '.join(map(str, args)), deadline=deadline)


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] != '--':
        sys.exit('usage: release_network.py -- COMMAND [ARG ...]')
    try:
        run(sys.argv[2:], capture=False, timeout=1800)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, TimeoutError) as exc:
        if getattr(exc, 'stderr', None):
            print(exc.stderr, file=sys.stderr, end='')
        sys.exit(str(exc))
