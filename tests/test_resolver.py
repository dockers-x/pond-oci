import base64
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("resolver", Path(__file__).resolve().parents[1] / "scripts/resolve-rootfs.py")
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)
DIGEST = "a" * 64
REVISION = "b" * 40
SOURCE = (
    f'ROOTFS_SHA256 = "{DIGEST}"\n'
    'ROOTFS_URL = f"https://releases.butterfly.so/rootfs/{ROOTFS_SHA256}/pond-rootfs.tar.zst"\n'
)


class ResolverTests(unittest.TestCase):
    def test_repository_endpoint_has_no_trailing_slash(self):
        with patch.object(resolver, "urlopen", return_value=io.BytesIO(b'{"default_branch":"main"}')) as opener:
            self.assertEqual(resolver.api("")["default_branch"], "main")
            self.assertEqual(opener.call_args.args[0].full_url, "https://api.github.com/repos/bflycomputer/iso-installer")

    def test_reads_only_whitelisted_declarations_without_executing_source(self):
        source = "raise RuntimeError('must not execute')\n" + SOURCE
        url, digest = resolver.declaration(source)
        self.assertEqual(digest, DIGEST)
        self.assertIn(DIGEST, url)

    def test_refuses_calls_and_untrusted_domains(self):
        for source in (
            SOURCE.replace('{ROOTFS_SHA256}', '{str(ROOTFS_SHA256)}'),
            SOURCE.replace('releases.butterfly.so', 'example.invalid'),
            SOURCE.replace('"a' + 'a' * 63 + '"', '"bad"'),
            SOURCE + 'ROOTFS_SHA256 = "' + DIGEST + '"\n',
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                resolver.declaration(source)

    def test_pins_revision_before_reading_the_declaration(self):
        calls = []

        def fetch(path):
            calls.append(path)
            return {
                "": {"default_branch": "main"},
                "commits/main": {"sha": REVISION},
                f"contents/src/backend/model.py?ref={REVISION}": {
                    "type": "file", "encoding": "base64",
                    "content": base64.b64encode(SOURCE.encode()).decode(),
                },
            }[path]

        source = resolver.resolve(fetch)
        self.assertEqual(calls[-1], f"contents/src/backend/model.py?ref={REVISION}")
        self.assertEqual(source["metadata"]["upstream_revision"], REVISION)

    def test_same_artifact_does_not_churn_lock_for_new_installer_commits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rootfs.lock.json"
            source = {"schema_version": 1, "url": "fixture", "sha256": DIGEST, "metadata": {"revision": "old"}}
            self.assertTrue(resolver.update(path, source))
            previous = path.read_bytes()
            source["metadata"]["revision"] = "new"
            self.assertFalse(resolver.update(path, source))
            self.assertEqual(previous, path.read_bytes())

    def test_check_never_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            self.assertTrue(resolver.update(path, {"url": "fixture", "sha256": DIGEST}, check=True))
            self.assertFalse(path.exists())

    def test_changed_digest_updates_the_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock.json"
            source = {"schema_version": 1, "url": "fixture", "sha256": DIGEST}
            resolver.update(path, source)
            source["sha256"] = "c" * 64
            self.assertTrue(resolver.update(path, source))
            self.assertEqual(json.loads(path.read_text())["sha256"], "c" * 64)


if __name__ == "__main__":
    unittest.main()
