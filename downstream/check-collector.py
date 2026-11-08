#!/usr/bin/env python3
"""Report native Linux collector build prerequisites or trusted binary dependencies."""
import argparse
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys


def command(args):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, check=False)
    except OSError as error:
        print(f'{args[0]}: {error}', file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', nargs='?', type=Path,
                        help='check a trusted collector binary instead of build prerequisites')
    args = parser.parse_args()
    print(f'Host: {platform.system()} {platform.machine()} ({platform.platform()})')
    libc, version = platform.libc_ver()
    print(f'Libc: {libc or "unknown"} {version or "unknown"}')
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'aarch64', 'arm64'):
        print('Unsupported host: collector packaging supports Linux x86_64 and aarch64.', file=sys.stderr)
        return 1

    if args.binary is not None:
        if not args.binary.is_file():
            print(f'Not a regular file: {args.binary}', file=sys.stderr)
            return 1
        print('Checking loader dependencies of trusted binary with ldd:')
        result = command(['ldd', str(args.binary.resolve())])
        if result is None:
            return 1
        print(result.stdout, end='')
        if result.returncode or 'not found' in result.stdout:
            return 1
        print('Loader dependencies resolved on this host; this does not establish compatibility elsewhere.')
        return 0

    ok = True
    for executable in ('cmake', 'pkg-config'):
        path = shutil.which(executable)
        print(f'{executable}: {path or "missing"}')
        ok &= path is not None
    compiler = shutil.which('c++')
    print(f'C++ compiler: {compiler or "missing"} (C++20 required)')
    ok &= compiler is not None
    if compiler:
        result = command([compiler, '--version'])
        if result is None or result.returncode:
            ok = False
        else:
            print(result.stdout.splitlines()[0])
    if shutil.which('cmake'):
        result = command(['cmake', '--version'])
        match = re.search(r'cmake version (\d+)\.(\d+)', result.stdout) if result else None
        if not match or result.returncode or tuple(map(int, match.groups())) < (3, 22):
            print('CMake 3.22 or newer is required.', file=sys.stderr)
            ok = False
        else:
            print(result.stdout.splitlines()[0])
    if shutil.which('pkg-config'):
        for package in ('libzstd', 'libbrotlidec', 'sqlite3', 'icu-uc', 'openssl', 'libcurl'):
            result = command(['pkg-config', '--modversion', package])
            if result is None or result.returncode:
                print(f'{package}: missing development package', file=sys.stderr)
                ok = False
            else:
                print(f'{package}: {result.stdout.strip()}')
    print('This diagnostic does not compile C++20 or establish runtime compatibility on another host.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
