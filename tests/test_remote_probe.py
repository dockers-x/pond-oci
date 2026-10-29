import importlib.util
import base64
import hashlib
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


class InstalledBinaryTests(unittest.TestCase):
    def test_installed_binary_is_verified_without_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "reviewed"
            installed = root / "installed"
            expected.write_bytes(b"reviewed binary")
            installed.write_bytes(expected.read_bytes())
            installed.chmod(0o755)
            before = installed.stat()
            result = probe.stage_binary(expected, installed, installed=True)
            self.assertEqual(result["mode"], "verify-installed")
            self.assertEqual(result["sha256"], hashlib.sha256(expected.read_bytes()).hexdigest())
            after = installed.stat()
            self.assertEqual((after.st_ino, after.st_mode, after.st_mtime_ns, after.st_ctime_ns),
                             (before.st_ino, before.st_mode, before.st_mtime_ns, before.st_ctime_ns))

    def test_installed_mode_rejects_different_missing_or_symlink_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "reviewed"
            installed = root / "installed"
            expected.write_bytes(b"reviewed binary")
            with self.assertRaisesRegex(RuntimeError, "installed"):
                probe.stage_binary(expected, installed, installed=True)
            installed.write_bytes(b"different binary")
            installed.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, "installed"):
                probe.stage_binary(expected, installed, installed=True)
            self.assertEqual(installed.read_bytes(), b"different binary")
            installed.unlink()
            installed.symlink_to(expected)
            with self.assertRaisesRegex(RuntimeError, "installed"):
                probe.stage_binary(expected, installed, installed=True)

    def test_staging_mode_still_refuses_to_replace_existing_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "reviewed"
            installed = root / "installed"
            expected.write_bytes(b"reviewed binary")
            installed.write_bytes(b"upstream payload")
            with self.assertRaisesRegex(RuntimeError, "replace"):
                probe.stage_binary(expected, installed, installed=False)
            self.assertEqual(installed.read_bytes(), b"upstream payload")


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


class RemoteCaptureTests(unittest.TestCase):
    def capture_fixture(self, painted_delay):
        server, client = socket.socketpair()
        stopped = threading.Event()
        failures = []

        def serve():
            try:
                with server:
                    server.settimeout(3)
                    header = bytearray()
                    while not header.endswith(b"\r\n\r\n"):
                        header.extend(probe.read_exact(server, 1))
                    key = next(line.split(b":", 1)[1].strip() for line in header.split(b"\r\n") if line.startswith(b"Sec-WebSocket-Key:"))
                    acceptance = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
                    server.sendall(b"HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: " + acceptance + b"\r\n\r\n")
                    messages = [
                        (1, b'{"type":"ready","resize":false,"resize_scale":false}'),
                        (1, b'{"type":"frame_id","id":1}'),
                        (2, b"\x01\xff\xd8uniform"),
                        (1, b'{"type":"frame_id","id":2}'),
                        (2, b"\x01\xff\xd8painted"),
                    ]
                    for opcode, content in messages:
                        if content.endswith(b"painted"):
                            time.sleep(painted_delay)
                        server.sendall(bytes((0x80 | opcode, len(content))) + content)
                    stopped.wait(timeout=5)
            except Exception as error:
                failures.append(error)

        worker = threading.Thread(target=serve)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "frame.jpg"
                def decode(content):
                    return {"width": 1280, "height": 720, "colors": 1 if content.endswith(b"uniform") else 300}
                with patch.object(probe.socket, "create_connection", return_value=client), patch.object(probe, "decoded_frame", side_effect=decode, create=True), patch.object(probe, "send_frame", wraps=probe.send_frame) as sent:
                    probe.capture(1234, destination)
                self.assertEqual(destination.read_bytes(), b"\xff\xd8painted", "a uniform first JPEG is not a painted desktop")
                messages = [json.loads(call.args[2]) for call in sent.call_args_list if call.args[1] == 1]
                acknowledgements = [message for message in messages if message.get("type") == "frame_ack"]
                self.assertEqual(acknowledgements, [{"type": "frame_ack", "id": 1}, {"type": "frame_ack", "id": 2}])
        finally:
            stopped.set()
            worker.join(timeout=5)
            client.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])

    def test_capture_waits_for_a_painted_frame_and_acknowledges_each_candidate(self):
        self.capture_fixture(0)

    def test_capture_accepts_a_painted_frame_after_the_initial_socket_timeout(self):
        self.capture_fixture(2.2)


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
