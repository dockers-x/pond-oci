"""Check selected metadata from the actual single-layer desktop candidate."""

import argparse
import json
from pathlib import Path
import posixpath


def resolve(selected, path):
    for _attempt in range(40):
        components = path.split("/")
        for index in range(len(components)):
            prefix = "/".join(components[:index + 1])
            entry = selected.get(prefix, {})
            if entry.get("kind") == "symlink":
                path = posixpath.normpath(posixpath.join("/" + posixpath.dirname(prefix), entry["link_target"], *components[index + 1:])).lstrip("/")
                break
        else:
            entry = selected.get(path, {})
            if entry.get("kind") == "hardlink":
                path = posixpath.normpath("/" + entry["link_target"]).lstrip("/")
                continue
            return entry
    raise ValueError("candidate contains an unresolved link cycle")


def check(report, masks):
    selected = {entry["path"]: entry for entry in report["selected"]}
    forbidden = (
        ".oci-kit-staging", "etc/lightos/seed.env", "etc/lightos/remote-desktop.env",
        "etc/machine-id", "etc/pacman.d/gnupg", "var/lib/lightos/initialized",
        "var/lib/oci-kit", "home/pond-ci",
    )
    for path in selected:
        if any(path == prefix or path.startswith(prefix + "/") for prefix in forbidden):
            raise ValueError(f"candidate retained build or instance state: {path}")
    for path in (
        "usr/local/bin/lighos-init", "usr/lib/lightos-remoted/lightos-remoted",
        "usr/lib/systemd/systemd", "usr/bin/niri", "usr/bin/qs",
    ):
        entry = resolve(selected, path)
        if entry.get("kind") != "file" or entry.get("uid") != 0 or not entry.get("mode", 0) & 0o111 or entry.get("size", 0) == 0:
            raise ValueError(f"candidate lacks a root-owned executable: {path}")
    for unit in masks:
        path = f"etc/systemd/system/{unit}"
        if selected.get(path, {}).get("kind") != "symlink" or selected[path].get("link_target") != "/dev/null":
            raise ValueError(f"candidate unit is not masked: {unit}")
    if selected.get("etc/systemd/system/default.target", {}).get("link_target") != "/usr/lib/systemd/system/multi-user.target":
        raise ValueError("candidate does not select the container systemd target")
    for path in (
        "etc/skel/.config/niri/config.kdl",
        "etc/oci-kit/lightos.toml",
        "usr/lib/systemd/system-generators/lighos-init-generator",
        "usr/lib/systemd/system/lightos-remote-desktop.service",
        "usr/lib/systemd/system/lightos-remote-desktop-session.service",
        "etc/systemd/system/lighos-init.service",
        "etc/systemd/system/multi-user.target.wants/lighos-init.service",
        "etc/systemd/system/lightos-remote-desktop.service.d/20-oci-kit-post-setup.conf",
        "etc/systemd/system/lightos-remote-desktop-session.service.d/20-oci-kit-post-setup.conf",
    ):
        if not resolve(selected, path):
            raise ValueError(f"candidate lost a required desktop/init path: {path}")
    if report["text"].get("etc/lightos/remote-desktop-native.env") != "LIGHTOS_REMOTE_DESKTOP_COMPOSITOR=niri\n":
        raise ValueError("candidate does not explicitly select the native Pond compositor")
    return {"scope": "single-layer desktop candidate, not LightOS boot/proxy", "checked_masks": len(masks), "desktop": "niri", "instance_state_absent": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    print(json.dumps(check(json.loads(arguments.report.read_text()), (repository / "profiles/masked-units.txt").read_text().splitlines()), indent=2))
