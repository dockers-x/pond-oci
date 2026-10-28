import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "lightos-remote-desktop.service",
    "lightos-remote-desktop-session.service",
)


@unittest.skipUnless(os.environ.get("LIGHTOS_INIT_BINARY"), "requires the GitHub-built Rust toolkit")
class LightOSProfileTests(unittest.TestCase):
    def test_the_actual_pond_profile_orders_both_services_without_activating_them(self):
        for settings_present in (False, True):
            with self.subTest(settings_present=settings_present):
                self.assert_offline_install_preserves_platform_ownership(settings_present)

    def assert_offline_install_preserves_platform_ownership(self, settings_present):
        initializer = os.environ["LIGHTOS_INIT_BINARY"]
        cleaner = os.environ["ROOTFS_CLEANER_BINARY"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "rootfs"
            root.mkdir()
            vendor_units = root / "usr/lib/systemd/system"
            vendor_units.mkdir(parents=True)
            environment = root / "etc/lightos/remote-desktop.env"
            if settings_present:
                environment.parent.mkdir(parents=True)
                environment.write_text("opaque platform-owned fixture\n")
                environment.chmod(0o600)
            for service in SERVICES:
                (vendor_units / service).write_text("opaque package-owned fixture\n")
            commands = [
                [cleaner, "mark", "--root", str(root)],
                [initializer, "install", "--root", str(root), "--config", str(ROOT / "profiles/lightos.toml")],
            ]
            for command in commands + commands[1:]:
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=20,
                    env={"PATH": "/no-commands-during-offline-install"},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            for service in SERVICES:
                drop_in = root / f"etc/systemd/system/{service}.d/20-oci-kit-post-setup.conf"
                self.assertTrue(drop_in.is_file(), f"missing ordering for {service}")
                self.assertEqual(drop_in.read_text(), "[Unit]\nRequires=lighos-init.service\nAfter=lighos-init.service\n")
                self.assertEqual((vendor_units / service).read_text(), "opaque package-owned fixture\n")
                for relative in (f"etc/systemd/system/{service}", f"etc/systemd/system/multi-user.target.wants/{service}"):
                    path = root / relative
                    self.assertFalse(path.exists() or path.is_symlink())
            generator = root / "usr/lib/systemd/system-generators/lighos-init-generator"
            self.assertTrue(generator.is_symlink(), "missing Rust render-group generator")
            self.assertEqual(generator.readlink(), Path("/usr/local/bin/lighos-init"))
            self.assertFalse((root / "run/systemd/generator").exists())
            unit = (root / "etc/systemd/system/lighos-init.service").read_text()
            self.assertIn("AssertPathExists=/var/lib/lightos/initialized", unit)
            self.assertNotIn("ConditionPathExists=/var/lib/lightos/initialized", unit)
            if settings_present:
                self.assertEqual(environment.read_text(), "opaque platform-owned fixture\n")
                self.assertEqual(environment.stat().st_mode & 0o777, 0o600)
            else:
                self.assertFalse(environment.exists() or environment.is_symlink())
            self.assertFalse((root / "var/lib/oci-kit").exists())
            self.assertFalse((root / "var/lib/lightos/initialized").exists())
