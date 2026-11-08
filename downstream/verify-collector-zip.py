#!/usr/bin/env python3
"""Verify the shipped macOS zip contains the exact executable Linux collector."""
import argparse
import filecmp
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile

MEMBER = 'Agent Speed.app/Contents/Resources/collectors/linux-x86_64/agent-speed-collector'


def verify(archive, expected):
    with zipfile.ZipFile(archive) as zipped:
        matches = [item for item in zipped.infolist() if item.filename == MEMBER]
        if len(matches) != 1:
            raise ValueError(f'expected exactly one {MEMBER} in the zip')
        info = matches[0]
        mode = info.external_attr >> 16
        if info.create_system != 3 or not stat.S_ISREG(mode) or not mode & 0o111:
            raise ValueError('collector must be a regular file with Unix executable permissions in the zip')

    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(['unzip', '-qq', str(Path(archive).resolve()), MEMBER, '-d', directory], check=True)
        extracted = Path(directory) / MEMBER
        if extracted.is_symlink() or not extracted.is_file() or not os.access(extracted, os.X_OK):
            raise ValueError('extracted collector is not an executable regular file')
        if not filecmp.cmp(extracted, expected, shallow=False):
            raise ValueError('extracted collector differs from the supplied artifact')

def verify_windows(archive, expected):
    member = 'collectors/linux-x86_64/agent-speed-collector'
    digest = hashlib.sha256(Path(expected).read_bytes()).digest()
    with zipfile.ZipFile(archive) as zipped:
        matches = [item for item in zipped.infolist() if item.filename.replace('\\', '/') == member]
        if len(matches) != 1 or matches[0].is_dir():
            raise ValueError(f'expected exactly one {member} in the zip')
        with zipped.open(matches[0]) as stream:
            actual = hashlib.file_digest(stream, 'sha256').digest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(stream.read()).digest()
        if actual != digest:
            raise ValueError('Windows collector differs from the supplied artifact')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('collector', type=Path)
    parser.add_argument('--windows', action='store_true', help='verify a Windows bundle')
    args = parser.parse_args()
    try:
        (verify_windows if args.windows else verify)(args.archive, args.collector)
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(f'Collector verification failed: {error}', file=sys.stderr)
        return 1
    print('Zip contains the executable collector with matching bytes.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
