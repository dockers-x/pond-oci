import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


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
            {"namespace": "pond-lookalike", "layer": "Top"},
            {"namespace": "quickshell-unrelated", "layer": "Top"},
        ]), [])
        for name in ("quickshell",):
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

    def graphical_fixture(self, directory):
        root = directory / "root"
        report = directory / "report"
        root.mkdir()
        report.mkdir()
        probe = PROBE.Probe(root, report)
        process = mock.Mock()
        process.poll.return_value = None
        endpoint = root / "run/user/1000/niri.wayland-0.42.sock"
        for name, replacement in (
            ("stop", mock.Mock()),
            ("niri_socket", mock.Mock(return_value=endpoint)),
            ("copy_screenshot", mock.Mock()),
        ):
            patcher = mock.patch.object(PROBE, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(PROBE.subprocess, "Popen", return_value=process)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(PROBE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "1280 720 2048", ""))
        patcher.start()
        self.addCleanup(patcher.stop)
        probe.command = mock.Mock(return_value=["fixture-command"])
        probe.run = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "diagnostic", ""))
        return probe

    def test_colorful_wallpaper_does_not_hide_a_panel_that_died_after_first_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            probe = self.graphical_fixture(Path(directory))
            queries = 0

            def respond(_endpoint, message):
                nonlocal queries
                if message == "Layers":
                    queries += 1
                    return {"Layers": [{"namespace": "quickshell", "layer": "Top"}] if queries == 1 else []}
                if message == "Outputs":
                    return {"Outputs": {"winit": {}}}
                return "Handled"

            with mock.patch.object(PROBE, "request", side_effect=respond), self.assertRaises(RuntimeError):
                probe.graphical_session("99")

    def test_optional_launcher_diagnostic_timeout_preserves_verified_frame_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            probe = self.graphical_fixture(Path(directory))
            probe.run.side_effect = subprocess.TimeoutExpired(["qs", "ipc", "show"], 15, output=b"partial diagnostic")

            def respond(_endpoint, message):
                if message == "Layers":
                    return {"Layers": [{"namespace": "quickshell", "layer": "Top"}]}
                if message == "Outputs":
                    return {"Outputs": {"winit": {}}}
                return "Handled"

            with mock.patch.object(PROBE, "request", side_effect=respond):
                evidence = probe.graphical_session("99")
            self.assertEqual(evidence["frame"]["colors"], 2048)
            self.assertTrue(evidence["launcher_ipc_diagnostic"]["timed_out"])
            self.assertIn("partial diagnostic", (probe.report / "pond-ipc.txt").read_text())
