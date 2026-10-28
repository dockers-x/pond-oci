"""Exercise only a disposable GitHub Pond rootfs, never the running host."""

import argparse
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import time


USER = "pond-ci"
USER_ID = 1000
CONFIG = f"/home/{USER}/.config/niri/config.kdl"


def validate_fixture(root, report, runner_temp):
    temporary = runner_temp.resolve(strict=True)
    for path in (root, report):
        if path == Path("/") or not path.is_absolute() or not path.resolve().is_relative_to(temporary):
            raise ValueError("fixture and report must be inside RUNNER_TEMP")
    marker = root / ".oci-kit-staging"
    if root.is_symlink() or not root.is_dir() or marker.is_symlink() or not marker.is_file():
        raise ValueError("root must be a marked disposable staging directory")
    if report.resolve().is_relative_to(root.resolve()) or root.resolve().is_relative_to(report.resolve()):
        raise ValueError("report and runtime root must be separate")


def decode_reply(document):
    if not isinstance(document, dict) or set(document) != {"Ok"}:
        raise ValueError(f"Niri IPC rejected request: {document!r}")
    return document["Ok"]


def fixture_directory(root, relative):
    directory = root
    for component in Path(relative).parts:
        if component in ("/", ".", ".."):
            raise ValueError("fixture directory must be relative and normalized")
        directory = directory / component
        directory.mkdir(mode=0o755, exist_ok=True)
        metadata = directory.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
            raise ValueError("fixture runtime directories must be controlled ordinary directories")
    return directory


def copy_screenshot(image, destination):
    descriptor = os.open(image, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != USER_ID or metadata.st_size > 8 * 1024 * 1024:
            raise ValueError("screenshot must be a bounded regular fixture-user file")
        with open(f"/proc/self/fd/{descriptor}", "rb") as source:
            content = source.read(8 * 1024 * 1024 + 1)
        if len(content) > 8 * 1024 * 1024 or not content.startswith(b"\x89PNG\r\n\x1a\n") or not content.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
            raise ValueError("screenshot is not a complete bounded PNG")
        destination.write_bytes(content)
    finally:
        os.close(descriptor)


def pond_layers(layers):
    if not isinstance(layers, list):
        raise ValueError("Niri layer response must be a list")
    return [layer for layer in layers if isinstance(layer, dict)
            and isinstance(layer.get("namespace"), str)
            and layer["namespace"] == "quickshell"
            and layer.get("layer") in ("Top", "Bottom", "Overlay")]


def request(path, message):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(str(path))
        connection.sendall(json.dumps(message).encode() + b"\n")
        with connection.makefile("rb") as stream:
            line = stream.readline(1024 * 1024 + 1)
        if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
            raise ValueError("unbounded or incomplete Niri IPC reply")
        return decode_reply(json.loads(line))


def niri_socket(root):
    runtime = root / f"run/user/{USER_ID}"
    expected = (root / "usr/bin/niri").stat()
    for path in sorted(runtime.glob("niri.*.sock")):
        metadata = path.lstat()
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != USER_ID:
            continue
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(1)
            connection.connect(str(path))
            process, owner, _group = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        executable = Path(f"/proc/{process}/exe").stat()
        process_root = Path(f"/proc/{process}/root").stat()
        fixture_root = root.stat()
        if owner == USER_ID and (executable.st_dev, executable.st_ino) == (expected.st_dev, expected.st_ino) \
                and (process_root.st_dev, process_root.st_ino) == (fixture_root.st_dev, fixture_root.st_ino):
            return path
    return None


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


class Probe:
    def __init__(self, root, report):
        self.root = root
        self.report = report
        self.environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        self.prefix = [
            shutil.which("bwrap"), "--unshare-pid", "--unshare-ipc", "--unshare-net",
            "--unshare-uts", "--hostname", "pond-ci", "--die-with-parent",
            "--bind", str(root), "/", "--proc", "/proc", "--dev", "/dev", "--clearenv",
            "--setenv", "PATH", "/usr/bin:/usr/sbin:/bin:/sbin",
            "--setenv", "LANG", "C.UTF-8",
        ]

    def command(self, arguments, user=False, extra=()):
        command = self.prefix + list(extra) + ["--"]
        if user:
            command += [
                "/usr/bin/setpriv", f"--reuid={USER_ID}", f"--regid={USER_ID}", "--init-groups",
                "--no-new-privs", "/usr/bin/env", f"HOME=/home/{USER}", f"USER={USER}",
                f"LOGNAME={USER}", f"XDG_RUNTIME_DIR=/run/user/{USER_ID}",
            ]
        return command + list(arguments)

    def run(self, arguments, user=False, timeout=120, extra=(), check=True):
        result = subprocess.run(
            self.command(arguments, user, extra), capture_output=True, text=True,
            timeout=timeout, env=self.environment,
        )
        with (self.report / "commands.log").open("a") as output:
            output.write(json.dumps(arguments) + "\n" + result.stdout[-16000:] + result.stderr[-16000:] + "\n")
        if check and result.returncode:
            raise RuntimeError(f"fixture command failed: {arguments[0]}: {result.stderr[-4000:]}")
        return result

    def initialize(self):
        for program in ("niri", "qs", "setpriv", "dbus-run-session", "useradd", "pacman-key"):
            path = self.root / f"usr/bin/{program}"
            if not path.is_file() and not path.is_symlink():
                raise RuntimeError(f"required payload program is absent: {program}")
        self.run(["/usr/bin/dbus-uuidgen", "--ensure=/etc/machine-id"])
        self.run(["/usr/bin/rm", "-rf", "--", "/etc/pacman.d/gnupg"])
        self.run(["/usr/bin/install", "-d", "-m", "700", "/etc/pacman.d/gnupg"])
        self.run(["/usr/bin/pacman-key", "--init"], timeout=240)
        self.run(["/usr/bin/pacman-key", "--populate", "archlinux"], timeout=240)
        self.run(["/usr/bin/useradd", "--create-home", "--user-group", "--uid", str(USER_ID), "--shell", "/usr/bin/bash", USER])
        if not (self.root / CONFIG.lstrip("/")).is_file():
            raise RuntimeError("real Pond skel did not provide the user's Niri config")
        marker = fixture_directory(self.root, "var/lib/lightos") / "initialized"
        if marker.exists() or marker.is_symlink():
            raise RuntimeError("fresh fixture unexpectedly retained a platform marker")
        marker.write_text("synthetic GitHub platform-prerequisite fixture\n")
        for changed in (True, False):
            result = self.run(["/usr/local/bin/lighos-init", "apply", "--apply"], timeout=240)
            if json.loads(result.stdout).get("changed") is not changed:
                raise RuntimeError("actual initializer did not satisfy first-run/idempotence contract")
        if (self.root / "etc/lightos/remote-desktop.env").exists():
            raise RuntimeError("initialization unexpectedly created remote authentication")
        if (self.root / f"home/{USER}").stat().st_uid != USER_ID:
            raise RuntimeError("platform-created home has incorrect ownership")
        directories = [f"/run/systemd/generator{suffix}" for suffix in ("", ".early", ".late")]
        for directory in directories:
            fixture_directory(self.root, directory.lstrip("/"))
        self.run(["/usr/lib/systemd/system-generators/lighos-init-generator", *directories])
        runtime = fixture_directory(self.root, f"run/user/{USER_ID}")
        runtime.chmod(0o700)
        os.chown(runtime, USER_ID, USER_ID)
        self.run(["/usr/bin/niri", "--config", CONFIG, "validate"], user=True)
        return {"first_apply_changed": True, "second_apply_changed": False, "home_uid": USER_ID}

    def desktop(self):
        read_descriptor, write_descriptor = os.pipe()
        with (self.report / "xvfb.log").open("wb") as log:
            display = subprocess.Popen(
                [shutil.which("Xvfb"), "-displayfd", str(write_descriptor), "-screen", "0", "1280x720x24", "-nolisten", "tcp", "-ac"],
                pass_fds=(write_descriptor,), stdout=log, stderr=log,
                env=self.environment, start_new_session=True,
            )
            os.close(write_descriptor)
            try:
                if not select.select([read_descriptor], [], [], 20)[0]:
                    raise RuntimeError("isolated parent display did not become ready")
                number = os.read(read_descriptor, 64).decode().strip()
                if not number.isdecimal():
                    raise RuntimeError("isolated parent display returned an invalid number")
                return self.graphical_session(number)
            finally:
                os.close(read_descriptor)
                stop(display)

    def graphical_session(self, display):
        parent_socket = f"/tmp/.X11-unix/X{display}"
        extra = [
            "--ro-bind", parent_socket, parent_socket,
            "--setenv", "DISPLAY", f":{display}",
            "--setenv", "LIBGL_ALWAYS_SOFTWARE", "1",
            "--setenv", "QT_QPA_PLATFORM", "wayland",
        ]
        command = self.command(["/usr/bin/dbus-run-session", "--", "/usr/bin/niri", "--config", CONFIG], user=True, extra=extra)
        with (self.report / "desktop.log").open("wb") as log:
            process = subprocess.Popen(command, stdout=log, stderr=log, env=self.environment, start_new_session=True)
            try:
                deadline = time.monotonic() + 90
                endpoint = None
                layers = []
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("real Pond desktop exited before readiness; inspect desktop.log")
                    try:
                        endpoint = niri_socket(self.root)
                        if endpoint:
                            layers = request(endpoint, "Layers").get("Layers", [])
                            if pond_layers(layers):
                                break
                    except (OSError, ValueError):
                        pass
                    time.sleep(0.5)
                else:
                    raise RuntimeError(f"real Pond shell did not map a panel; last layers={layers!r}")
                outputs = request(endpoint, "Outputs").get("Outputs", {})
                if not outputs:
                    raise RuntimeError("native Niri has no output")
                screenshot = f"/home/{USER}/pond-proof.png"
                reply = request(endpoint, {"Action": {"ScreenshotScreen": {"write_to_disk": True, "show_pointer": False, "path": screenshot}}})
                if reply != "Handled":
                    raise RuntimeError(f"screenshot request was not handled: {reply!r}")
                image = self.root / screenshot.lstrip("/")
                copied_image = self.report / "pond-desktop.png"
                until = time.monotonic() + 10
                while True:
                    try:
                        copy_screenshot(image, copied_image)
                        break
                    except (OSError, ValueError):
                        if time.monotonic() >= until:
                            raise RuntimeError("Niri did not publish a complete safe screenshot") from None
                        time.sleep(0.1)
                result = subprocess.run([shutil.which("identify"), "-limit", "memory", "128MiB", "-limit", "map", "256MiB", "-format", "%w %h %k", str(copied_image)], capture_output=True, text=True, timeout=10, check=True, env=self.environment)
                width, height, colors = map(int, result.stdout.split())
                if min(width, height) < 100 or colors < 16:
                    raise RuntimeError("desktop screenshot is missing, too small or uniform")
                native = "/" + endpoint.relative_to(self.root).as_posix()
                diagnostic = {"exit_code": None, "timed_out": False}
                try:
                    result = self.run(["/usr/bin/env", f"NIRI_SOCKET={native}", "/usr/bin/qs", "-c", "pond-shell", "ipc", "show"], user=True, timeout=15, check=False)
                    diagnostic["exit_code"] = result.returncode
                    fragments = (result.stdout, result.stderr)
                except subprocess.TimeoutExpired as error:
                    diagnostic["timed_out"] = True
                    fragments = (error.stdout, error.stderr)
                text = "".join(fragment.decode(errors="replace") if isinstance(fragment, bytes) else fragment or "" for fragment in fragments)
                (self.report / "pond-ipc.txt").write_text(text[-16000:])
                time.sleep(1)
                if process.poll() is not None:
                    raise RuntimeError("native Niri exited after its first frame")
                layers = request(endpoint, "Layers").get("Layers", [])
                if not pond_layers(layers):
                    raise RuntimeError("Pond shell panel disappeared after its first frame")
                return {"layers": layers, "outputs": outputs, "frame": {"width": width, "height": height, "colors": colors}, "launcher_ipc_diagnostic": diagnostic}
            finally:
                stop(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.geteuid() != 0:
        parser.error("this experiment requires an ephemeral GitHub runner as root")
    validate_fixture(arguments.root, arguments.report, Path(os.environ["RUNNER_TEMP"]))
    for program in ("bwrap", "Xvfb", "identify"):
        if not shutil.which(program):
            parser.error(f"missing runner dependency: {program}")
    arguments.report.mkdir(parents=True, exist_ok=True)
    probe = Probe(arguments.root, arguments.report)
    evidence = {"scope": "synthetic materialization and real Pond payload, not actual LightOS boot"}
    try:
        evidence["initialization"] = probe.initialize()
        evidence["desktop"] = probe.desktop()
    finally:
        (arguments.report / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
