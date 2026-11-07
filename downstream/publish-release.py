#!/usr/bin/env python3
"""Publish a trusted release, reconciling ambiguous GitHub write failures."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import release
import release_network as network


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    tag = os.environ['GITHUB_REF_NAME']
    sha = os.environ['GITHUB_SHA'].lower()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-fork\.[1-9][0-9]*)?', tag):
        raise ValueError('Invalid release tag')
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Invalid release commit SHA')
    base = f'repos/{repo}'

    def api(path, *, paginate=False):
        args = [release.GH, 'api']
        if paginate:
            args += ['--paginate', '--slurp']
        return json.loads(network.run(args + [base + path]))

    def verify_tag():
        obj = api('/git/ref/tags/' + tag)['object']
        seen = set()
        while obj['type'] == 'tag':
            if obj['sha'] in seen:
                raise RuntimeError('Cyclic annotated tag')
            seen.add(obj['sha'])
            obj = api('/git/tags/' + obj['sha'])['object']
        if obj['type'] != 'commit' or obj['sha'].lower() != sha:
            raise RuntimeError('Remote tag does not point to the expected commit')

    def get_release():
        pages = api('/releases?per_page=100', paginate=True)
        matches = [item for page in pages for item in page if item['tag_name'] == tag]
        if len(matches) > 1:
            raise RuntimeError('Multiple releases for tag')
        return matches[0] if matches else None

    def is_draft(item):
        if not isinstance(item.get('draft'), bool):
            raise RuntimeError('Unexpected release state')
        return item['draft']

    verify_tag()
    current = get_release()
    if current and not is_draft(current):
        print('Release is already published; leaving it unchanged.')
        return

    expected = release.assets_expected(tag[1:])
    paths = {path.name: path for path in Path('dist').iterdir() if path.is_file()}
    if set(paths) != expected:
        raise RuntimeError('Release assets do not match expected set: missing '
                           + ', '.join(sorted(expected - paths.keys())) + '; extra '
                           + ', '.join(sorted(paths.keys() - expected)))
    metadata = {}
    for name, path in paths.items():
        size = path.stat().st_size
        if not size:
            raise RuntimeError(f'Empty release asset: {name}')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        metadata[name] = (size, 'sha256:' + digest.hexdigest())

    def assets(item):
        # Listing assets separately ensures pagination and fresh state after writes.
        pages = api(f"/releases/{item['id']}/assets?per_page=100", paginate=True)
        result = {}
        for page in pages:
            for asset in page:
                if asset['name'] in result:
                    raise RuntimeError('Duplicate release asset: ' + asset['name'])
                result[asset['name']] = asset
        return result

    def matches(asset, name):
        size, digest = metadata[name]
        return (asset.get('state') == 'uploaded' and asset.get('size') == size
                and asset.get('digest') == digest)

    def verify_published(item):
        verify_tag()
        if is_draft(item) or item.get('prerelease') is not False:
            raise RuntimeError('Release is not formally published')
        found = assets(item)
        if set(found) != expected or any(not matches(found[n], n) for n in expected):
            raise RuntimeError('Published release assets do not match expected assets')

    def retry_write(operation, reconcile, label):
        try:
            network.retry(operation, label=label)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            if not network.is_transient(exc) or not reconcile():
                raise

    def created():
        verify_tag()
        item = get_release()
        if not item:
            return False
        if not is_draft(item):
            verify_published(item)
        return True

    def uploaded(name):
        verify_tag()
        item = get_release()
        if not item:
            return False
        if not is_draft(item):
            verify_published(item)
            return True
        found = assets(item)
        if name not in found:
            return False
        if not matches(found[name], name):
            raise RuntimeError(f'Conflicting asset {name}; resolve it manually while the release remains unpublished')
        return True

    def published():
        verify_tag()
        item = get_release()
        if not item or is_draft(item):
            return False
        verify_published(item)
        return True

    def create():
        verify_tag()
        item = get_release()
        if item:
            if not is_draft(item):
                verify_published(item)
            return
        network.run_once([release.GH, 'release', 'create', tag, '--repo', repo, '--draft',
                          '--title', 'Agent Speed ' + tag, '--generate-notes', '--verify-tag'])

    if not current:
        retry_write(create, created, 'create draft release')
    current = get_release()
    if not current:
        raise RuntimeError('Draft release was not created')
    if not is_draft(current):
        verify_published(current)
        return

    for name in sorted(expected):
        def upload():
            verify_tag()
            item = get_release()
            if not item:
                raise RuntimeError('Release disappeared before upload')
            if not is_draft(item):
                verify_published(item)
                return
            found = assets(item)
            if name in found:
                if matches(found[name], name):
                    return
                raise RuntimeError(f'Conflicting asset {name}; resolve it manually while the release remains unpublished')
            try:
                network.run_once([release.GH, 'release', 'upload', tag, str(paths[name]),
                                  '--repo', repo])
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr or ''
                if isinstance(stderr, bytes):
                    stderr = stderr.decode(errors='replace')
                if re.search(r'\b(?:409|422)\b', stderr) and uploaded(name):
                    return
                raise
        retry_write(upload, lambda: uploaded(name), 'upload ' + name)

    def publish():
        verify_tag()
        item = get_release()
        if not item:
            raise RuntimeError('Release disappeared before publication')
        if not is_draft(item):
            verify_published(item)
            return
        found = assets(item)
        if set(found) != expected or any(not matches(found[n], n) for n in expected):
            raise RuntimeError('Draft release assets do not match expected assets')
        network.run_once([release.GH, 'release', 'edit', tag, '--repo', repo,
                          '--draft=false', '--prerelease=false'])

    retry_write(publish, published, 'publish release')
    item = get_release()
    if not item:
        raise RuntimeError('Release disappeared after publication')
    verify_published(item)


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Publication failed: {exc}', file=sys.stderr)
        sys.exit(1)
