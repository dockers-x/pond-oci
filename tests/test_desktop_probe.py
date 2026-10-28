import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/probe-desktop.py"
SPEC = importlib.util.spec_from_file_location("desktop_probe", SCRIPT)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class DesktopProbeTests(unittest.TestCase):
    def test_empty_compositor_and_wallpaper_do_not_pass_as_the_pond_shell(self):
        self.assertEqual(PROBE.pond_layers([]), [])
        self.assertEqual(PROBE.pond_layers([
            {"namespace": "swww", "layer": "Background"},
            {"namespace": "quickshell", "layer": "Background"},
            {"namespace": "unrelated-pond", "layer": "Top"},
            {"namespace": "another-panel", "layer": "Top"},
        ]), [])
        for name in ("pond-shell", "quickshell", "PondPanel"):
            layer = {"namespace": name, "layer": "Top"}
            self.assertEqual(PROBE.pond_layers([layer]), [layer])

    def test_niri_errors_and_malformed_replies_cannot_be_readiness(self):
        self.assertEqual(PROBE.decode_reply({"Ok": {"Layers": []}}), {"Layers": []})
        for document in ({"Err": "not ready"}, {}, [], {"Ok": {}, "Err": "failure"}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                PROBE.decode_reply(document)

    def test_live_root_unmarked_root_and_overlapping_report_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "root"
            root.mkdir()
            report = temporary / "report"
            with self.assertRaises(ValueError):
                PROBE.validate_fixture(Path("/"), report, temporary)
            with self.assertRaises(ValueError):
                PROBE.validate_fixture(root, report, temporary)
            (root / ".oci-kit-staging").write_text("fixture intent marker")
            PROBE.validate_fixture(root, report, temporary)
            with self.assertRaises(ValueError):
                PROBE.validate_fixture(root, root / "report", temporary)
            linked = temporary / "linked"
            linked.symlink_to(root)
            with self.assertRaises(ValueError):
                PROBE.validate_fixture(linked, report, temporary)

    def test_runtime_directory_links_are_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "root"
            outside = temporary / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "run").symlink_to(outside)
            with self.assertRaises(ValueError):
                PROBE.fixture_directory(root, "run/user/1000")
            self.assertEqual(list(outside.iterdir()), [])

    def test_screenshot_links_cannot_escape_the_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            outside = temporary / "outside"
            outside.write_text("do not read through screenshot links")
            image = temporary / "image.png"
            image.symlink_to(outside)
            destination = temporary / "copied.png"
            with self.assertRaises(ValueError):
                PROBE.copy_screenshot(image, destination)
            self.assertFalse(destination.exists())
