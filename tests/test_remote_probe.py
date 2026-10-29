import importlib.util
from pathlib import Path
import socket
import struct
import unittest


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


if __name__ == "__main__":
    unittest.main()
