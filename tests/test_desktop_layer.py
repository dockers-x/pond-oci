import copy
import importlib.util
from pathlib import Path
import unittest


specification = importlib.util.spec_from_file_location("desktop_layer", Path(__file__).resolve().parents[1] / "scripts/check-desktop-layer.py")
checker = importlib.util.module_from_spec(specification)
specification.loader.exec_module(checker)


class DesktopLayerTests(unittest.TestCase):
    def setUp(self):
        self.masks = ["sddm.service", "seatd.service"]
        executable_paths = [
            "usr/local/bin/lighos-init", "usr/lib/lightos-remoted/lightos-remoted",
            "usr/lib/systemd/systemd", "usr/bin/niri", "usr/bin/quickshell",
        ]
        ordinary_paths = [
            "usr/share/pond-interface/niri/config.kdl",
            "etc/oci-kit/lightos.toml",
            "usr/lib/systemd/system/lightos-remote-desktop.service",
            "usr/lib/systemd/system/lightos-remote-desktop-session.service",
            "usr/lib/systemd/system/multi-user.target",
            "etc/systemd/system/lighos-init.service",
            "etc/systemd/system/lightos-remote-desktop.service.d/20-oci-kit-post-setup.conf",
            "etc/systemd/system/lightos-remote-desktop-session.service.d/20-oci-kit-post-setup.conf",
        ]
        entries = [{"path": path, "kind": "file", "uid": 0, "gid": 0, "mode": 0o755 if path in executable_paths else 0o644, "size": 16} for path in executable_paths + ordinary_paths]
        links = {
            "usr/bin/qs": "quickshell",
            "usr/lib/systemd/system-generators/lighos-init-generator": "/usr/local/bin/lighos-init",
            "etc/skel/.config/niri": "/usr/share/pond-interface/niri",
            "etc/systemd/system/default.target": "/usr/lib/systemd/system/multi-user.target",
            "etc/systemd/system/multi-user.target.wants/lighos-init.service": "../lighos-init.service",
            **{f"etc/systemd/system/{unit}": "/dev/null" for unit in self.masks},
        }
        entries.extend({"path": path, "kind": "symlink", "uid": 0, "gid": 0, "mode": 0o777, "size": 0, "link_target": target} for path, target in links.items())
        self.report = {"selected": entries, "text": {"etc/lightos/remote-desktop-native.env": "LIGHTOS_REMOTE_DESKTOP_COMPOSITOR=niri\n"}}

    def test_accepts_native_desktop_with_original_directory_and_relative_links(self):
        result = checker.check(self.report, self.masks)
        self.assertEqual(result["desktop"], "niri")
        self.assertEqual(result["checked_masks"], 2)

    def test_rejects_runtime_auth_and_initialized_state(self):
        for path in ("etc/lightos/remote-desktop.env", "home/pond-ci/.config/auth", "var/lib/oci-kit/lightos-init.json", "etc/pacman.d/gnupg/private-keys-v1.d/key"):
            with self.subTest(path=path):
                report = copy.deepcopy(self.report)
                report["selected"].append({"path": path, "kind": "file"})
                with self.assertRaisesRegex(ValueError, "instance state"):
                    checker.check(report, self.masks)

    def test_rejects_a_missing_mask(self):
        self.report["selected"] = [entry for entry in self.report["selected"] if entry["path"] != "etc/systemd/system/seatd.service"]
        with self.assertRaisesRegex(ValueError, "not masked"):
            checker.check(self.report, self.masks)

    def test_rejects_a_dangling_compositor_alias(self):
        self.report["selected"] = [entry for entry in self.report["selected"] if entry["path"] != "usr/bin/quickshell"]
        with self.assertRaisesRegex(ValueError, "root-owned executable"):
            checker.check(self.report, self.masks)

    def test_rejects_a_missing_original_niri_config(self):
        self.report["selected"] = [entry for entry in self.report["selected"] if entry["path"] != "usr/share/pond-interface/niri/config.kdl"]
        with self.assertRaisesRegex(ValueError, "required desktop/init path"):
            checker.check(self.report, self.masks)

    def test_rejects_link_cycles_without_touching_the_host_filesystem(self):
        selected = {"loop": {"kind": "symlink", "link_target": "loop"}}
        with self.assertRaisesRegex(ValueError, "link cycle"):
            checker.resolve(selected, "loop/config.kdl")

    def test_rejects_a_non_root_runtime_binary(self):
        for entry in self.report["selected"]:
            if entry["path"] == "usr/lib/lightos-remoted/lightos-remoted":
                entry["uid"] = 1000
        with self.assertRaisesRegex(ValueError, "root-owned executable"):
            checker.check(self.report, self.masks)


if __name__ == "__main__":
    unittest.main()
