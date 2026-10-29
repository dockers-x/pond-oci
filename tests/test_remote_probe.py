import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


specification = importlib.util.spec_from_file_location("remote_probe", Path(__file__).resolve().parents[1] / "scripts/probe-remote-desktop.py")
probe = importlib.util.module_from_spec(specification)
specification.loader.exec_module(probe)


class RemoteFrameTests(unittest.TestCase):
    def frame(self, encoded):
        server, client = socket.socketpair()
        with server, client:
            client.settimeout(1)
            server.sendall(encoded)
            server.shutdown(socket.SHUT_WR)
            return probe.receive_frame(client)

    def test_small_server_frame(self):
        self.assertEqual(self.frame(b"\x81\x02{}"), (1, b"{}"))

    def test_extended_server_frame(self):
        content = b"x" * 256
        self.assertEqual(self.frame(b"\x82\x7e" + struct.pack("!H", len(content)) + content), (2, content))

    def test_oversized_frame_rejected_before_reading_its_body(self):
        with self.assertRaisesRegex(RuntimeError, "oversized"):
            self.frame(b"\x82\x7f" + struct.pack("!Q", 32 * 1024 * 1024 + 1))

    def test_truncated_frame_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "complete frame"):
            self.frame(b"\x82\x05abc")

    def test_unsupported_flags_rejected(self):
        for header in (b"\x01\x00", b"\xc1\x00", b"\x81\x80"):
            with self.subTest(header=header), self.assertRaisesRegex(RuntimeError, "flags"):
                self.frame(header)


class ProcessStopTests(unittest.TestCase):
    def test_already_exited_process_is_not_a_normal_stop(self):
        for status in (0, 17):
            with self.subTest(status=status):
                process = subprocess.Popen([sys.executable, "-c", f"raise SystemExit({status})"])
                process.wait(timeout=5)
                with self.assertRaisesRegex(RuntimeError, "exited before"):
                    probe.stop(process)

    def test_nonzero_exit_after_term_is_not_a_normal_stop(self):
        source = "import signal,sys; signal.signal(signal.SIGTERM, lambda *_: sys.exit(19)); print('ready', flush=True); signal.pause()"
        with subprocess.Popen([sys.executable, "-c", source], stdout=subprocess.PIPE, text=True) as process:
            try:
                self.assertEqual(process.stdout.readline(), "ready\n")
                with self.assertRaisesRegex(RuntimeError, "unsuccessful"):
                    probe.stop(process)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)

    def test_successful_term_after_live_readiness(self):
        source = "import signal,sys; signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); print('ready', flush=True); signal.pause()"
        with subprocess.Popen([sys.executable, "-c", source], stdout=subprocess.PIPE, text=True) as process:
            try:
                self.assertEqual(process.stdout.readline(), "ready\n")
                probe.stop(process)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        source = "import signal,sys; signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); print('ready', flush=True); signal.pause()"
        self.process = subprocess.Popen([sys.executable, "-c", source], stdout=subprocess.PIPE, text=True)
        self.addCleanup(self.cleanup_process)
        self.assertEqual(self.process.stdout.readline(), "ready\n")

    def cleanup_process(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=5)
        self.process.stdout.close()

    def test_readiness_retries_a_timed_out_socket_while_owner_is_alive(self):
        sender, receiver = socket.socketpair()
        with sender, receiver:
            receiver.settimeout(0.02)
            delivery = threading.Timer(0.15, lambda: sender.sendall(b"ready"))
            delivery.start()
            try:
                probe.wait_for(self.process, lambda: receiver.recv(5) == b"ready", "not ready", timeout=2)
            finally:
                delivery.join(timeout=2)

    def test_persistent_probe_timeouts_fail_with_the_readiness_context(self):
        sender, receiver = socket.socketpair()
        attempts = []
        with sender, receiver:
            receiver.settimeout(0.02)
            def pending():
                attempts.append(time.monotonic())
                return receiver.recv(1) == b"ready"
            with self.assertRaisesRegex(RuntimeError, "Pond is not ready"):
                probe.wait_for(self.process, pending, "Pond is not ready", timeout=0.3)
            self.assertGreaterEqual(len(attempts), 2)

    def test_protocol_errors_are_not_converted_to_startup_readiness(self):
        def invalid():
            raise ValueError("invalid native protocol")
        with self.assertRaisesRegex(ValueError, "invalid native protocol"):
            probe.wait_for(self.process, invalid, "not ready", timeout=1)


class RuntimeDiagnosticTests(unittest.TestCase):
    def test_a_rejected_log_does_not_hide_the_other_child_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            report = root / "report"
            runtime.mkdir()
            report.mkdir()
            unrelated = root / "private-fixture"
            unrelated.write_text("not-for-diagnostics\n")
            (runtime / "desktop.log").symlink_to(unrelated)
            (runtime / "dbus.log").write_text("safe private-bus fixture\n")
            with patch.object(probe, "RUNTIME", runtime):
                errors = probe.runtime_diagnostics(report)
            self.assertEqual(errors[0]["file"], "desktop.log")
            self.assertFalse((report / "desktop.log").exists())
            self.assertEqual((report / "dbus.log").read_text(), "safe private-bus fixture\n")
            self.assertNotIn("not-for-diagnostics", str(errors))
            self.assertEqual(unrelated.read_text(), "not-for-diagnostics\n")

    def test_rejected_diagnostics_do_not_replace_the_primary_failure_or_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            report = root / "report"
            runtime.mkdir()
            report.mkdir()
            os.mkfifo(runtime / "desktop.log")
            evidence = {"phase": "native sidebar readiness"}
            with patch.object(probe, "RUNTIME", runtime), self.assertRaisesRegex(ValueError, "primary native failure"):
                try:
                    raise ValueError("primary native failure")
                finally:
                    evidence["diagnostic_errors"] = probe.runtime_diagnostics(report)
                    (report / "evidence.json").write_text(json.dumps(evidence))
            document = json.loads((report / "evidence.json").read_text())
            self.assertEqual(document["phase"], "native sidebar readiness")
            self.assertEqual(document["diagnostic_errors"][0]["file"], "desktop.log")


if __name__ == "__main__":
    unittest.main()
