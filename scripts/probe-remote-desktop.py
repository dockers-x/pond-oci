"""Run the accepted remote owner against a disposable real Pond payload on GitHub."""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time


specification = importlib.util.spec_from_file_location("pond_payload_probe", Path(__file__).with_name("probe-desktop.py"))
payload = importlib.util.module_from_spec(specification)
specification.loader.exec_module(payload)
BINARY = "/usr/lib/lightos-remoted/lightos-remoted"
RUNTIME = Path(f"/run/user/{payload.USER_ID}/desktop")
PASSWORD = "isolated-pond-remote-fixture"
FILES = ("evidence.json", "owner.log", "transport-1.log", "transport-2.log", "frame-1.jpg", "frame-2.jpg")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_exact(connection, length):
    result = bytearray()
    while len(result) < length:
        fragment = connection.recv(length - len(result))
        require(fragment, "remote connection ended before a complete frame")
        result.extend(fragment)
    return bytes(result)


def send_frame(connection, opcode, content):
    require(len(content) < 126, "fixture only sends small control messages")
    mask = os.urandom(4)
    masked = bytes(value ^ mask[index % 4] for index, value in enumerate(content))
    connection.sendall(bytes((0x80 | opcode, 0x80 | len(content))) + mask + masked)


def receive_frame(connection):
    first, second = read_exact(connection, 2)
    require(first & 0x80 and not first & 0x70 and not second & 0x80, "unsupported server frame flags")
    length = second & 127
    if length == 126:
        length = struct.unpack("!H", read_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(connection, 8))[0]
    require(length <= 32 * 1024 * 1024, "oversized remote frame")
    return first & 15, read_exact(connection, length)


def capture(port, destination):
    with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
        connection.settimeout(2)
        key = base64.b64encode(os.urandom(16)).decode()
        authorization = base64.b64encode(f"lightos:{PASSWORD}".encode()).decode()
        connection.sendall((f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: http://127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\nAuthorization: Basic {authorization}\r\n\r\n").encode())
        header = bytearray()
        while not header.endswith(b"\r\n\r\n"):
            require(len(header) < 32768, "oversized upgrade response")
            header.extend(read_exact(connection, 1))
        lines = header.decode("ascii").split("\r\n")
        require(lines[0].split()[1] == "101", "authenticated WebSocket upgrade was rejected")
        fields = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
        fields = {name.lower(): value.strip() for name, value in fields.items()}
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        require(fields.get("sec-websocket-accept") == expected, "invalid upgrade acceptance")
        ready = None
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            opcode, content = receive_frame(connection)
            if opcode == 9:
                send_frame(connection, 10, content)
            elif opcode == 1:
                message = json.loads(content)
                require(message.get("type") != "error", "remote transport reported an error")
                if message.get("type") == "ready":
                    require(message.get("resize") is False and message.get("resize_scale") is False, "native owner advertised unsupported resize")
                    ready = message
                    send_frame(connection, 1, b'{"type":"video","codec":"jpeg"}')
            elif opcode == 2 and content[:1] == b"\x01":
                require(ready is not None and content[1:3] == b"\xff\xd8", "frame was not a ready JPEG stream")
                destination.write_bytes(content[1:])
                send_frame(connection, 8, struct.pack("!H", 1000))
                return {name: ready.get(name) for name in ("desktop", "desktop_backend", "width", "height", "resize", "resize_scale")}
            elif opcode == 8:
                raise RuntimeError("remote transport closed before a JPEG frame")
        raise RuntimeError("remote transport did not deliver a frame before the fixture deadline")


def identity(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
    require(fields[0] not in ("Z", "X"), "desktop process is no longer live")
    return [pid, fields[19]]


def pond_processes():
    executable = Path("/usr/bin/qs").stat()
    matches = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            actual = (process / "exe").stat()
            arguments = (process / "cmdline").read_bytes().split(b"\0")
            if process.stat().st_uid == os.geteuid() and (actual.st_dev, actual.st_ino) == (executable.st_dev, executable.st_ino) and any(arguments[index:index + 2] == [b"-c", b"pond-shell"] for index in range(len(arguments))):
                matches.append(identity(int(process.name)))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return matches


def still_live(expected):
    try:
        return identity(expected[0]) == expected
    except (FileNotFoundError, ProcessLookupError, RuntimeError):
        return False


def stop(process):
    require(process.poll() is None, "desktop process exited before the requested normal stop")
    process.terminate()
    require(process.wait(timeout=10) == 0, "desktop process returned an unsuccessful status after normal stop")


def cleanup(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_for(process, predicate, message, timeout=40):
    deadline = time.monotonic() + timeout
    while not predicate():
        require(process.poll() is None and time.monotonic() < deadline, message)
        time.sleep(0.1)


def inside(report):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and Path("/.oci-kit-staging").is_file() and not Path("/.oci-kit-staging").is_symlink(), "inside mode requires a marked disposable GitHub rootfs")
    require(report == Path("/run/pond-remote-report") and Path(__file__).parent == Path("/run/pond-ci-src"), "inside mode refuses a non-fixture layout")
    require(os.geteuid() == payload.USER_ID, "remote fixture must use the disposable platform account")
    environment = dict(os.environ, LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe", WLR_RENDERER="pixman", LIGHTOS_REMOTE_DESKTOP_AUTH_USER="lightos", LIGHTOS_REMOTE_DESKTOP_AUTH_PASSWORD=PASSWORD)
    evidence = {"scope": "real Pond payload and native remote owner, not LightOS boot/proxy", "platform_proxy_tested": False, "launcher_app_start_tested": False}
    before = Path(payload.CONFIG).read_bytes()
    owner = None
    transport = None
    try:
        with (report / "owner.log").open("wb") as log:
            owner = subprocess.Popen([BINARY, "desktop-session", "--compositor", "niri", "--audio", "false", "--desktop-config", payload.CONFIG, "--runtime-dir", str(RUNTIME)], env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        wait_for(owner, lambda: (RUNTIME / "session.json").is_file(), "real Pond native owner failed startup")
        descriptor = json.loads((RUNTIME / "niri-environment.json").read_text())
        endpoint = Path(descriptor["niri_socket"])
        wayland = RUNTIME / descriptor["wayland_display"]
        peer_pid, peer_uid, _ = payload.socket_peer(endpoint)
        require(peer_uid == os.geteuid() and payload.socket_peer(wayland)[:2] == (peer_pid, peer_uid), "Pond sockets do not share the actual Niri peer")
        actual = Path(f"/proc/{peer_pid}/exe").stat()
        expected = Path("/usr/bin/niri").stat()
        require((actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino), "selected desktop peer is not native Niri")
        identities = [identity(owner.pid), identity(peer_pid)]
        wait_for(owner, lambda: payload.pond_layers(payload.request(endpoint, "Layers").get("Layers", [])), "original Pond sidebar never appeared")
        shell = pond_processes()
        require(shell, "original Pond Quickshell process identity is missing")
        identities.extend(shell)
        generations = []
        for generation in (1, 2):
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            with (report / f"transport-{generation}.log").open("wb") as log:
                transport = subprocess.Popen([BINARY, "serve", "--compositor", "niri", "--audio", "false", "--listen", "127.0.0.1", "--port", str(port), "--session-runtime", str(RUNTIME)], env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            def listening():
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        return True
                except OSError:
                    return False
            wait_for(transport, listening, "Pond transport never listened")
            generations.append(capture(port, report / f"frame-{generation}.jpg"))
            stop(transport)
            transport = None
            require([identity(expected[0]) for expected in identities] == identities, "transport restart changed the desktop or native shell")
            require(payload.pond_layers(payload.request(endpoint, "Layers").get("Layers", [])), "Pond shell disappeared on transport stop")
        require(Path(payload.CONFIG).read_bytes() == before, "remote startup changed the native Pond config")
        stop(owner)
        owner = None
        require(not (RUNTIME / "session.json").exists(), "normal owner stop left published readiness")
        deadline = time.monotonic() + 5
        while any(still_live(expected) for expected in identities):
            require(time.monotonic() < deadline, "normal owner shutdown left a live native desktop process before namespace fallback")
            time.sleep(0.1)
        evidence.update(generations=generations, identities=identities, native_config_preserved=True, pond_sidebar_preserved=True)
    finally:
        if transport is not None:
            cleanup(transport)
        if owner is not None:
            cleanup(owner)
        (report / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


def outside(arguments):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.geteuid() == 0, "remote probe only runs as root on an ephemeral GitHub runner")
    payload.validate_fixture(arguments.root, arguments.report, Path(os.environ["RUNNER_TEMP"]))
    require(arguments.binary.is_file() and not arguments.binary.is_symlink(), "fixture binary must be an ordinary GitHub build output")
    arguments.report.mkdir(parents=True, exist_ok=True)
    probe = payload.Probe(arguments.root, arguments.report)
    missing = []
    for program in ("niri", "qs", "cage", "python", "setpriv"):
        result = probe.run(["/usr/bin/test", "-x", f"/usr/bin/{program}"], timeout=15, check=False)
        if result.returncode:
            missing.append(program)
    require(not missing, f"real rootfs is missing remote prerequisites inside its own namespace: {', '.join(missing)}")
    binary = payload.fixture_directory(arguments.root, "usr/lib/lightos-remoted") / "lightos-remoted"
    require(not binary.exists() and not binary.is_symlink(), "fixture refuses to replace an upstream remote binary")
    shutil.copyfile(arguments.binary, binary)
    binary.chmod(0o755)
    source = payload.fixture_directory(arguments.root, "run/pond-ci-src")
    for name in ("probe-remote-desktop.py", "probe-desktop.py"):
        shutil.copyfile(Path(__file__).with_name(name), source / name)
    destination = payload.fixture_directory(arguments.root, "run/pond-remote-report")
    destination.chmod(0o700)
    os.chown(destination, payload.USER_ID, payload.USER_ID)
    initialized = probe.initialize()
    try:
        probe.run(["/usr/bin/env", "GITHUB_ACTIONS=true", "/usr/bin/python", "/run/pond-ci-src/probe-remote-desktop.py", "--inside", "--report", "/run/pond-remote-report"], user=True, timeout=180)
    finally:
        for name in FILES:
            path = destination / name
            if path.is_file() and not path.is_symlink():
                require(path.stat().st_size <= 64 * 1024 * 1024, "oversized fixture report")
                shutil.copyfile(path, arguments.report / name)
    evidence = json.loads((arguments.report / "evidence.json").read_text())
    evidence["initialization"] = initialized
    for generation in (1, 2):
        frame = arguments.report / f"frame-{generation}.jpg"
        result = subprocess.run(["identify", "-format", "%w %h %k", str(frame)], capture_output=True, text=True, timeout=15, check=True)
        width, height, colors = map(int, result.stdout.split())
        require(width >= 100 and height >= 100 and colors >= 256, "Pond remote stream was uniform or too small")
        evidence["generations"][generation - 1]["decoded_frame"] = {"width": width, "height": height, "colors": colors}
    (arguments.report / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--binary", type=Path)
    arguments = parser.parse_args()
    if arguments.inside:
        inside(arguments.report)
    else:
        require(arguments.root is not None and arguments.binary is not None, "root and binary are required outside the disposable namespace")
        outside(arguments)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
