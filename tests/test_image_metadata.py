import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REVISION = "c" * 40
KIT_REVISION = "b" * 40


class ImageMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.write_image()
        (self.root / "rootfs.lock.json").write_text(json.dumps({"schema_version": 1, "sha256": "a" * 64}))

    def write_image(self, version="0.1.0", kit_revision=KIT_REVISION):
        (self.root / "image.toml").write_text(
            f'schema_version = 1\nversion = "{version}"\nkit_revision = "{kit_revision}"\n'
        )

    def metadata(self, *arguments):
        return subprocess.run(
            ["python3", str(ROOT / "scripts/image-metadata.py"), "--root", str(self.root), "--revision", REVISION, *arguments],
            capture_output=True, text=True, timeout=10,
        )

    def test_untagged_build_has_a_semver_development_identity_and_locked_sources(self):
        result = self.metadata()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "schema_version": 1,
            "base_version": "0.1.0",
            "version": f"0.1.0-dev.g{REVISION[:12]}",
            "release": False,
            "recipe_revision": REVISION,
            "kit_revision": KIT_REVISION,
            "rootfs_sha256": "a" * 64,
        })

    def test_release_tag_must_match_the_declared_version_exactly(self):
        result = self.metadata("--release-tag", "v0.1.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        self.assertEqual(metadata["version"], "0.1.0")
        self.assertTrue(metadata["release"])
        for tag in ("v0.2.0", "main", "0.1.0", "v00.1.0", "v0.1.0-rc.1"):
            with self.subTest(tag=tag):
                result = self.metadata("--release-tag", tag)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("release tag", result.stderr)

    def test_numeric_revision_prefix_with_a_leading_zero_is_valid_semver(self):
        revision = "012345678901" + "a" * 28
        result = self.metadata("--revision", revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        version = json.loads(result.stdout)["version"]
        identifiers = version.split("-", 1)[1].split(".")
        for identifier in identifiers:
            self.assertFalse(identifier.isdecimal() and len(identifier) > 1 and identifier.startswith("0"), version)

    def test_formal_version_is_strict_semver_without_an_upstream_hash(self):
        for version in ("01.2.3", "1.2", "v1.2.3", "20261028", "a" * 64, "1.2.3+hash"):
            with self.subTest(version=version):
                self.write_image(version=version)
                result = self.metadata()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("version", result.stderr)

    def test_an_override_cannot_silently_replace_the_locked_toolkit(self):
        result = self.metadata("--kit-revision", "d" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("kit revision", result.stderr)
        result = self.metadata("--kit-revision", KIT_REVISION)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_source_identifiers_are_rejected(self):
        self.write_image(kit_revision="main")
        result = self.metadata()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("kit revision", result.stderr)
        self.write_image()
        (self.root / "rootfs.lock.json").write_text(json.dumps({"schema_version": 1, "sha256": "latest"}))
        result = self.metadata()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rootfs digest", result.stderr)

    def test_github_outputs_are_validated_values_not_shell_source(self):
        result = self.metadata("--release-tag", "v0.1.0", "--format", "github")
        self.assertEqual(result.returncode, 0, result.stderr)
        outputs = dict(line.split("=", 1) for line in result.stdout.splitlines())
        self.assertEqual(outputs["version"], "0.1.0")
        self.assertEqual(outputs["release"], "true")
        self.assertEqual(outputs["kit_revision"], KIT_REVISION)


if __name__ == "__main__":
    unittest.main()
