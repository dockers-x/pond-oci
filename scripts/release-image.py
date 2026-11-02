#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def command(*arguments):
    return subprocess.run(arguments, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            checksum.update(chunk)
    return checksum.hexdigest()


def validate_config(config, plan):
    labels = config['config']['Labels']
    expected = {
        'org.opencontainers.image.version': plan['version'],
        'org.opencontainers.image.revision': plan['identity']['recipe_revision'],
        'so.butterfly.rootfs.sha256': plan['identity']['rootfs_sha256'],
        'eu.ca-x.oci-kit.revision': plan['identity']['kit_revision'],
        'eu.ca-x.lightos-remoted.revision': plan['identity']['remoted_revision'],
    }
    if (config.get('architecture') != 'amd64' or config.get('os') != 'linux'
            or config['config'].get('Cmd') != ['/sbin/init']
            or config['config'].get('StopSignal') != 'SIGRTMIN+3'
            or any(labels.get(key) != value for key, value in expected.items())):
        raise ValueError('image config does not match the resolved release plan')


def missing_manifest(error):
    return re.search(rb'manifest unknown|name unknown|manifest_unknown|name_unknown', error, re.I) is not None


def receipt(repository, tag):
    release = json.loads(command('gh', 'api', f'repos/{repository}/releases/tags/{tag}'))
    asset = next(asset for asset in release['assets'] if asset['name'] == 'release.json')
    return json.loads(command('gh', 'api', '-H', 'Accept: application/octet-stream',
                              f'repos/{repository}/releases/assets/{asset["id"]}'))


def prepare(plan, directory, repository, images):
    directory.mkdir()
    old = receipt(repository, plan['tag']) if plan['mode'] != 'build' else None
    if old and (old['identity'] != plan['identity'] or old['images'] != images):
        raise ValueError('existing release source or registry targets differ')
    if plan['mode'] == 'existing':
        (directory / 'release.json').write_text(json.dumps(old, indent=2) + '\n')
        return
    archive = directory / 'pond-desktop.oci.tar'
    from_artifact = True
    try:
        command('gh', 'run', 'download', str(plan['artifact_run']), '--repo', repository,
                '--name', 'pond-desktop-amd64-candidate', '--dir', str(directory))
    except subprocess.CalledProcessError:
        if not old:
            raise
        from_artifact = False
        for image in images:
            try:
                command('skopeo', 'copy', '--preserve-digests',
                        f'docker://{image}@sha256:{old["manifest_sha256"]}', f'oci-archive:{archive}')
                break
            except subprocess.CalledProcessError:
                archive.unlink(missing_ok=True)
        else:
            raise ValueError('pending artifact expired and neither registry has its exact digest')
    image = f'oci-archive:{archive}'
    manifest = command('skopeo', 'inspect', '--raw', image)
    config = command('skopeo', 'inspect', '--config', '--raw', image)
    validate_config(json.loads(config), plan)
    if old and (digest(manifest) != old['manifest_sha256'] or digest(config) != old['config_sha256']
                or (from_artifact and file_digest(archive) != old['archive_sha256'])):
        raise ValueError('pending image no longer matches its immutable receipt')
    command('sudo', 'skopeo', 'copy', image, f'docker-daemon:pond-systemd-ci:{os.environ["GITHUB_RUN_ID"]}')
    command('sudo', 'env', 'GITHUB_ACTIONS=true', f'GITHUB_SERVER_URL={os.environ["GITHUB_SERVER_URL"]}',
            f'RUNNER_TEMP={os.environ["RUNNER_TEMP"]}', f'GITHUB_RUN_ID={os.environ["GITHUB_RUN_ID"]}',
            'bash', 'scripts/probe-systemd.sh', f'pond-systemd-ci:{os.environ["GITHUB_RUN_ID"]}')
    result = old or dict(schema_version=1, version=plan['version'], identity=plan['identity'],
                        source=plan['source'], artifact_run=plan['artifact_run'], images=images,
                        manifest_sha256=digest(manifest), config_sha256=digest(config),
                        archive_sha256=file_digest(archive))
    (directory / 'release.json').write_text(json.dumps(result, indent=2) + '\n')
    (directory / 'config.json').write_bytes(config)
    (directory / 'manifest.sha256').write_text(result['manifest_sha256'] + '\n')
    (directory / 'archive.sha256').write_text(result['archive_sha256'] + '  pond-desktop.oci.tar\n')


def publish(plan, directory, repository, images, auth):
    record = json.loads((directory / 'release.json').read_text())
    tag = plan['tag']
    if plan['mode'] != 'existing':
        try:
            reference = json.loads(command('gh', 'api', f'repos/{repository}/git/ref/tags/{tag}'))
        except subprocess.CalledProcessError as error:
            if b'HTTP 404' not in error.stderr:
                raise
            reference = json.loads(command('gh', 'api', '--method', 'POST', f'repos/{repository}/git/refs',
                                           '-f', f'ref=refs/tags/{tag}', '-f', f'sha={plan["identity"]["recipe_revision"]}'))
        if reference['object']['type'] != 'commit' or reference['object']['sha'] != plan['identity']['recipe_revision']:
            raise ValueError('refusing to move an existing release tag')
        if plan['mode'] == 'build':
            notes = directory / 'notes.md'
            notes.write_text(
                f'Pond Desktop {tag} — experimental linux/amd64\n\n'
                'Automatically resolved from upstream; only its hash is provided, so this image uses independent SemVer.\n\n'
                'Verified: final rootfs metadata/hardlinks, native Niri/Pond shell, two transport frames, '
                'actual systemd boot and synthetic platform/Rust initializer idempotence.\n\n'
                'Still unverified: real LightOS external proxy/auth, launcher interaction, physical VT/GPU. '
                'Optional native FFmpeg worker is not included. No stable/latest tags.\n\n'
                f'Upstream SHA256: {plan["identity"]["rootfs_sha256"]}\n\n'
                + '\n'.join(f'{image}:{plan["version"]}@sha256:{record["manifest_sha256"]}' for image in images) + '\n')
            assets = [str(directory / name) for name in ('release.json', 'config.json', 'archive.sha256', 'manifest.sha256')]
            command('gh', 'release', 'create', tag, '--repo', repository, '--verify-tag', '--draft',
                    '--prerelease', '--title', f'Pond Desktop {tag}', '--notes-file', str(notes), *assets)
    for image in images:
        target = f'docker://{image}:{plan["version"]}'
        try:
            remote = command('skopeo', 'inspect', '--authfile', auth, '--raw', target)
        except subprocess.CalledProcessError as error:
            if plan['mode'] == 'existing' or not missing_manifest(error.stderr):
                raise
            command('skopeo', 'copy', '--authfile', auth, '--preserve-digests',
                    f'oci-archive:{directory / "pond-desktop.oci.tar"}', target)
            remote = command('skopeo', 'inspect', '--authfile', auth, '--raw', target)
        if digest(remote) != record['manifest_sha256']:
            raise ValueError(f'refusing different existing manifest: {image}')
        config = command('skopeo', 'inspect', '--authfile', auth, '--config', '--raw', target)
        if digest(config) != record['config_sha256']:
            raise ValueError(f'remote raw config differs: {image}')
        validate_config(json.loads(config), plan)
    if plan['mode'] != 'existing':
        command('gh', 'release', 'edit', tag, '--repo', repository, '--draft=false', '--prerelease')
    state = json.loads(command('gh', 'release', 'view', tag, '--repo', repository, '--json', 'isDraft,isPrerelease'))
    if state['isDraft'] or not state['isPrerelease']:
        raise ValueError('release visibility/channel does not match the published image')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write(f'## Published {tag}\n\n')
        for image in images:
            summary.write(f'- `{image}:{plan["version"]}@sha256:{record["manifest_sha256"]}`\n')
    print(f'Verified both registries and GitHub prerelease: {tag}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'publish'))
    arguments = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        parser.error('release must run on GitHub main')
    plan = json.loads(os.environ['RELEASE_PLAN'])
    directory = Path(os.environ['RUNNER_TEMP']) / 'pond-release'
    repository = os.environ['GITHUB_REPOSITORY']
    images = [f'docker.io/{os.environ["DOCKERHUB_IMAGE"]}', f'ghcr.io/{repository.lower()}']
    if arguments.phase == 'prepare':
        prepare(plan, directory, repository, images)
    else:
        publish(plan, directory, repository, images, os.environ['REGISTRY_AUTH_FILE'])


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.stderr.buffer.write(error.stderr[-12000:])
        raise SystemExit(error.returncode)
