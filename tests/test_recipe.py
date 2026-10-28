from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RecipeTests(unittest.TestCase):
    def test_cleanup_rules_are_explicit_relative_paths_with_reasons(self):
        policy = tomllib.loads((ROOT / "profiles/cleanup.toml").read_text())
        self.assertEqual(policy["schema_version"], 1)
        paths = []
        for rule in policy["remove"]:
            path = Path(rule["path"])
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertTrue(rule["reason"])
            paths.append(rule["path"])
        self.assertEqual(len(paths), len(set(paths)))
        self.assertNotIn("usr/lib/modules", paths)
        self.assertNotIn("nix", paths)
        self.assertNotIn("etc/skel", paths)

    def test_masked_units_cannot_escape_the_unit_directory(self):
        units = (ROOT / "profiles/masked-units.txt").read_text().splitlines()
        self.assertEqual(len(units), len(set(units)))
        for unit in units:
            self.assertIsNotNone(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9@_.-]*\.(service|socket|timer|path)", unit))
        self.assertIn("sddm.service", units)
        self.assertIn("ufw.service", units)
        self.assertNotIn("sshd.service", units)
        self.assertNotIn("dbus.service", units)

    def test_init_profile_has_no_user_credentials(self):
        profile = tomllib.loads((ROOT / "profiles/lightos.toml").read_text())
        self.assertEqual(profile, {"schema_version": 1, "pacman_keyrings": ["pond"]})

    def test_build_downloads_the_reviewed_lock_without_refreshing_it(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text()
        downloads = re.findall(r"run: (bash pond-oci/scripts/fetch-rootfs\.sh[^\n]*)", workflow)
        self.assertEqual(downloads, ["bash pond-oci/scripts/fetch-rootfs.sh --locked"])

    def run_mask_loop(self, contents, failing_unit=""):
        dockerfile = (ROOT / "Dockerfile").read_text().replace("\\\n", "")
        match = re.search(r"while IFS= read -r unit.*?done < /work/profiles/masked-units\.txt", dockerfile, re.S)
        self.assertIsNotNone(match, "the production masking command must be exercised")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            units = temporary / "units"
            calls = temporary / "calls"
            units.write_text(contents)
            fake_ln = temporary / "ln"
            fake_ln.write_text(
                '#!/bin/sh\n'
                'printf "%s\\n" "$3" >> "$MASK_CALLS"\n'
                'if [ "$3" = "/rootfs/etc/systemd/system/${FAIL_UNIT:-}" ]; then exit 1; fi\n'
            )
            fake_ln.chmod(0o755)
            environment = dict(os.environ, PATH=f"{temporary}:{os.defpath}", MASK_CALLS=str(calls), FAIL_UNIT=failing_unit)
            command = match.group().replace("/work/profiles/masked-units.txt", shlex.quote(str(units)))
            result = subprocess.run(["/bin/sh", "-c", command], env=environment, capture_output=True, text=True, timeout=5)
            return result, calls.read_text().splitlines() if calls.exists() else []

    def test_mask_failure_cannot_be_hidden_by_a_later_success(self):
        result, calls = self.run_mask_loop("fail.service\nok.service\n", "fail.service")
        self.assertNotEqual(result.returncode, 0, "a failed mask must fail the build")
        self.assertEqual(calls, ["/rootfs/etc/systemd/system/fail.service"])

    def test_mask_list_without_a_final_newline_is_fully_processed(self):
        result, calls = self.run_mask_loop("final.service")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["/rootfs/etc/systemd/system/final.service"])


if __name__ == "__main__":
    unittest.main()
