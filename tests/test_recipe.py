from pathlib import Path
import re
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


if __name__ == "__main__":
    unittest.main()
