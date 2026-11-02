#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-rc\.[1-9][0-9]*)?')


def plan(source, revision, image, tags, releases):
    identity = dict(rootfs_sha256=source['sha256'], recipe_revision=revision,
                    kit_revision=image['kit_revision'], remoted_revision=image['remoted_revision'])
    if any(not re.fullmatch(r'[0-9a-f]{64}' if key == 'rootfs_sha256' else r'[0-9a-f]{40}', value)
           for key, value in identity.items()):
        raise ValueError('invalid immutable source identity')
    for release in releases:
        receipt = release.get('receipt', {})
        if receipt.get('identity') == identity:
            tag = release['tag_name']
            if not TAG.fullmatch(tag) or receipt.get('version') != tag[1:]:
                raise ValueError('release receipt/tag mismatch')
            if any(not isinstance(receipt.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', receipt[key])
                   for key in ('manifest_sha256', 'config_sha256', 'archive_sha256')):
                raise ValueError('invalid recorded image digest')
            if type(receipt.get('artifact_run')) is not int or receipt['artifact_run'] <= 0:
                raise ValueError('invalid recorded artifact run')
            result = {key: receipt[key] for key in ('version', 'manifest_sha256', 'config_sha256', 'archive_sha256', 'artifact_run')}
            return dict(result, identity=identity, source=source, tag=tag,
                        mode='resume' if release['draft'] else 'existing')
    versions = [tuple(map(int, match.groups())) for tag in tags if (match := TAG.fullmatch(tag))]
    base = tuple(map(int, image['version'].split('.')))
    highest = max([base, *versions])
    next_version = highest if not versions else (*highest[:2], highest[2] + 1)
    version = '.'.join(map(str, next_version)) + '-rc.1'
    return dict(mode='build', version=version, tag=f'v{version}', identity=identity, source=source)


def gh(*arguments):
    return subprocess.check_output(['gh', *arguments], text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        parser.error('release must be dispatched on GitHub main')
    spec = importlib.util.spec_from_file_location('resolver', ROOT / 'scripts/resolve-rootfs.py')
    resolver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resolver)
    source = resolver.resolve()
    repository = os.environ['GITHUB_REPOSITORY']
    tags = json.loads(gh('api', f'repos/{repository}/tags?per_page=100', '--paginate', '--slurp'))
    tags = [tag['name'] for page in tags for tag in page]
    pages = json.loads(gh('api', f'repos/{repository}/releases?per_page=100', '--paginate', '--slurp'))
    releases = [release for page in pages for release in page]
    for release in releases:
        assets = [asset for asset in release['assets'] if asset['name'] == 'release.json']
        if assets:
            release['receipt'] = json.loads(gh('api', '-H', 'Accept: application/octet-stream',
                                               f'repos/{repository}/releases/assets/{assets[0]["id"]}'))
    image = tomllib.loads((ROOT / 'image.toml').read_text())
    result = plan(source, os.environ['GITHUB_SHA'], image, tags, releases)
    if result['mode'] == 'build':
        result['artifact_run'] = int(os.environ['GITHUB_RUN_ID'])
    arguments.output.write_text(json.dumps(result, indent=2) + '\n')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'mode={result["mode"]}\nplan={json.dumps(result, separators=(",", ":"))}\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write(f'## {result["tag"]}: {result["mode"]}\n\nUpstream SHA256: `{source["sha256"]}`\n')


if __name__ == '__main__':
    main()
