#!/usr/bin/env python3
"""Stage a Linux collector and release provenance; optionally verify a trusted build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


NAME = 'agent-speed-collector-linux-x86_64'


def readelf(binary, option):
    return subprocess.run(['readelf', option, str(binary)], check=True, text=True,
                          stdout=subprocess.PIPE, env={**os.environ, 'LC_ALL': 'C'}).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--maintenance-commit', required=True)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('config.json'))
    parser.add_argument('--build-environment', default='unknown')
    parser.add_argument('--verify-shared-identity', action='store_true',
                        help='execute only a trusted production collector to verify its shared identity')
    args = parser.parse_args()

    header = readelf(args.binary, '-h')
    if not re.search(r'Machine:\s+Advanced Micro Devices X86-64\s*$', header, re.MULTILINE):
        raise ValueError('collector must be an x86_64 ELF executable')
    if not re.search(r'Class:\s+ELF64\s*$', header, re.MULTILINE):
        raise ValueError('collector must be a 64-bit ELF executable')
    program_headers = readelf(args.binary, '-l')
    if not re.search(r'Type:\s+(?:EXEC|DYN)\b', header):
        raise ValueError('collector must be an ELF executable or position-independent executable')
    dynamic = readelf(args.binary, '-d')
    versions = readelf(args.binary, '--version-info')
    interpreter = re.search(r'Requesting program interpreter: ([^\]]+)', program_headers)
    needed = re.findall(r'\(NEEDED\).*\[([^\]]+)\]', dynamic)
    # Version needs, not version definitions exported by the executable.
    needs = versions.partition('Version needs section')[2]
    version_needs = sorted(set(re.findall(r'Name: (\S+)', needs)))
    config = json.loads(args.config.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / NAME
    shutil.copyfile(args.binary, target)
    target.chmod(0o755)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    shared_identity = None
    if args.verify_shared_identity:
        # Execute the staged bytes, not a potentially different source path.
        result = subprocess.run([str(target.resolve()), '--identity'], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        expected = f'shared-collector-v2 {digest}\n'.encode('ascii')
        if result.stdout != expected:
            raise ValueError('collector identity does not match the staged executable SHA-256')
        shared_identity = {'command': '--identity', 'prefix': 'shared-collector-v2',
                           'sha256': digest}
    (args.output / (NAME + '.sha256')).write_text(f'{digest}  {NAME}\n')
    metadata = {
        'format_version': 1,
        'release_tag': args.tag,
        'maintenance_commit': args.maintenance_commit,
        'upstream_commit': config['upstream_commit'],
        'os': 'linux',
        'architecture': 'x86_64',
        'protocol': {'transport': 'newline-delimited JSON over stdio', 'version': 1,
                     'compatibility': 'same-release desktop clients; no cross-release compatibility guarantee'},
        'runtime': {'build_environment': args.build_environment, 'elf_interpreter': interpreter.group(1) if interpreter else None,
                    'elf_needed': needed, 'elf_version_needs': version_needs,
                    'compatibility': 'observed ELF requirements, not a cross-host compatibility guarantee'},
        'sha256': digest,
    }
    if shared_identity is not None:
        metadata['protocol']['shared_collector'] = {
            'control_version': 2,
            'capabilities': ['live_activity_v2', 'shared_collector_v1'],
            'identity': shared_identity,
        }
    (args.output / (NAME + '.json')).write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
