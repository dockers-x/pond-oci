import importlib.util
import unittest
from pathlib import Path


class ReleaseCandidateTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/release-candidate.py'
        spec = importlib.util.spec_from_file_location('release_candidate', path)
        self.release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.release)

    def test_rc_version_is_tied_to_the_declared_base(self):
        self.assertEqual(self.release.version('v0.1.0-rc.1', '0.1.0', '0.1.0-rc.1'), '0.1.0-rc.1')
        for tag in ('v0.1.0', 'v0.1.0-rc.2', 'v0.2.0-rc.1', 'v0.1.0-rc.01', 'v0.1.0-rc.0', 'main'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.release.version(tag, '0.1.0', '0.1.0-rc.1')

    def test_only_the_version_label_may_change(self):
        original = {'architecture': 'amd64', 'rootfs': {'diff_ids': ['sha256:abc']},
                    'config': {'Cmd': ['/sbin/init'], 'Labels': {'org.opencontainers.image.version': 'dev'}}}
        import copy
        promoted = copy.deepcopy(original)
        promoted['config']['Labels']['org.opencontainers.image.version'] = '0.1.0-rc.1'
        self.release.verify_config(original, promoted, '0.1.0-rc.1')
        for section, key, value in (('rootfs', 'diff_ids', ['sha256:changed']),
                                    ('config', 'Cmd', ['/bin/bash'])):
            changed = copy.deepcopy(promoted)
            changed[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.release.verify_config(original, changed, '0.1.0-rc.1')
        with self.assertRaises(ValueError):
            self.release.verify_config(original, promoted, '0.1.0-rc.2')
        original['config']['Healthcheck'] = {'Test': ['CMD', 'true']}
        with self.assertRaises(ValueError):
            self.release.verify_config(original, promoted, '0.1.0-rc.1')
