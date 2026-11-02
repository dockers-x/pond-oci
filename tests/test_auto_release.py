import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess
import json
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_plan', ROOT / 'scripts/plan-release.py')
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)
spec = importlib.util.spec_from_file_location('release_image', ROOT / 'scripts/release-image.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class AutoReleaseTests(unittest.TestCase):
    def setUp(self):
        self.source = {'sha256': 'a' * 64, 'url': 'https://example.org/rootfs.tar.zst'}
        self.image = dict(version='0.1.0', kit_revision='b' * 40, remoted_revision='c' * 40)

    def plan(self, tags=(), releases=()):
        return planner.plan(self.source, 'd' * 40, self.image, tags, releases)

    def test_allocates_above_all_existing_tags_without_mutating_them(self):
        self.assertEqual(self.plan(['v0.1.0-rc.1', 'v0.1.4', 'unrelated'])['tag'], 'v0.1.5-rc.1')
        self.assertEqual(self.plan()['tag'], 'v0.1.0-rc.1')
        self.assertEqual(self.plan(['v1.0.9-rc.1'])['tag'], 'v1.0.10-rc.1')

    def test_existing_release_is_noop_but_draft_resumes_the_exact_digest(self):
        receipt = self.plan(['v0.1.4'])
        receipt.update(manifest_sha256='e' * 64, config_sha256='f' * 64,
                       archive_sha256='0' * 64, artifact_run=123)
        release = dict(tag_name=receipt['tag'], draft=False, receipt=receipt)
        self.assertEqual(self.plan([receipt['tag']], [release])['mode'], 'existing')
        release['draft'] = True
        resumed = self.plan([receipt['tag']], [release])
        self.assertEqual(resumed['mode'], 'resume')
        self.assertEqual(resumed['artifact_run'], 123)
        self.assertEqual(resumed['manifest_sha256'], 'e' * 64)
        changed = copy.deepcopy(release)
        changed['receipt']['identity']['rootfs_sha256'] = '1' * 64
        self.assertEqual(self.plan([receipt['tag']], [changed])['tag'], 'v0.1.6-rc.1')

    def test_corrupt_receipts_fail_instead_of_rebuilding_over_existing_images(self):
        receipt = self.plan()
        receipt.update(manifest_sha256='bad')
        with self.assertRaises(ValueError):
            self.plan([receipt['tag']], [dict(tag_name=receipt['tag'], draft=True, receipt=receipt)])

    def test_source_revision_and_hash_are_validated(self):
        self.source['sha256'] = 'latest'
        with self.assertRaises(ValueError):
            self.plan()

    def test_all_receipt_digests_and_artifact_run_are_validated(self):
        receipt = self.plan()
        receipt.update(manifest_sha256='e' * 64, config_sha256='f' * 64,
                       archive_sha256='0' * 64, artifact_run=123)
        for key, value in [('config_sha256', 'bad'), ('archive_sha256', None),
                           ('artifact_run', True), ('artifact_run', 0)]:
            broken = dict(receipt, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.plan([receipt['tag']], [dict(tag_name=receipt['tag'], draft=True, receipt=broken)])

    def test_release_lookup_only_treats_404_as_missing(self):
        with patch.object(publisher, 'receipt', return_value={'version': '0.1.5-rc.1'}):
            self.assertEqual(publisher.existing_receipt('owner/repo', 'tag'), {'version': '0.1.5-rc.1'})
        for message in (b'HTTP 404', b'HTTP 403', b'HTTP 429'):
            error = subprocess.CalledProcessError(1, ['gh'], stderr=message)
            with patch.object(publisher, 'receipt', side_effect=error):
                if message == b'HTTP 404':
                    self.assertIsNone(publisher.existing_receipt('owner/repo', 'tag'))
                else:
                    with self.assertRaises(subprocess.CalledProcessError):
                        publisher.existing_receipt('owner/repo', 'tag')

    def test_completed_release_rejects_missing_or_moved_tag(self):
        plan = dict(self.plan(), mode='existing')
        missing = subprocess.CalledProcessError(1, ['gh'], stderr=b'HTTP 404')
        moved = json.dumps({'object': {'type': 'commit', 'sha': 'e' * 40}}).encode()
        for outcome in (missing, moved):
            with patch.object(publisher, 'command', side_effect=[outcome]) as command:
                with self.assertRaises(ValueError):
                    publisher.verify_tag(plan, 'owner/repo')
                self.assertEqual(command.call_count, 1)

    def test_failed_publish_job_reuses_existing_draft_without_recreating_it(self):
        plan = self.plan()
        manifest = b'{"schemaVersion":2}'
        config = b'{}'
        record = dict(manifest_sha256=publisher.digest(manifest), config_sha256=publisher.digest(config))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'release.json').write_text(json.dumps(record))
            def command(*arguments):
                if arguments[:2] == ('skopeo', 'inspect'):
                    return config if '--config' in arguments else manifest
                if arguments[:3] == ('gh', 'release', 'view'):
                    return b'{"isDraft":false,"isPrerelease":true}'
                if arguments[:3] == ('gh', 'release', 'edit'):
                    return b''
                self.fail(f'unexpected mutation: {arguments}')
            with patch.object(publisher, 'verify_tag'), \
                    patch.object(publisher, 'existing_receipt', return_value=record), \
                    patch.object(publisher, 'validate_config'), \
                    patch.object(publisher, 'command', side_effect=command), \
                    patch.dict(os.environ, GITHUB_STEP_SUMMARY=str(directory / 'summary')):
                publisher.publish(plan, directory, 'owner/repo', ['docker.io/owner/image', 'ghcr.io/owner/image'], 'auth')
            self.assertIn(plan['tag'], (directory / 'summary').read_text())

    def test_auth_and_network_errors_are_not_missing_tags(self):
        self.assertTrue(publisher.missing_manifest(b'manifest unknown'))
        for error in (b'unauthorized', b'denied', b'HTTP 429', b'connection timeout'):
            self.assertFalse(publisher.missing_manifest(error))

    def test_actual_image_config_must_match_the_full_planned_identity(self):
        plan = self.plan()
        labels = {
            'org.opencontainers.image.version': plan['version'],
            'org.opencontainers.image.revision': 'd' * 40,
            'so.butterfly.rootfs.sha256': 'a' * 64,
            'eu.ca-x.oci-kit.revision': 'b' * 40,
            'eu.ca-x.lightos-remoted.revision': 'c' * 40,
        }
        config = dict(architecture='amd64', os='linux', config=dict(
            Cmd=['/sbin/init'], StopSignal='SIGRTMIN+3', Labels=labels))
        publisher.validate_config(config, plan)
        for key in labels:
            changed = copy.deepcopy(config)
            changed['config']['Labels'][key] = 'wrong'
            with self.subTest(key=key), self.assertRaises(ValueError):
                publisher.validate_config(changed, plan)

    def test_only_one_manual_release_entrypoint_remains(self):
        workflows = ROOT / '.github/workflows'
        self.assertEqual(sorted(path.name for path in workflows.glob('*.yml')),
                         ['_build-desktop.yml', 'release.yml', 'validate.yml'])
        self.assertIn('workflow_dispatch:', (workflows / 'release.yml').read_text())
        self.assertNotIn('workflow_dispatch:', (workflows / '_build-desktop.yml').read_text())
        self.assertNotIn('workflow_dispatch:', (workflows / 'validate.yml').read_text())
