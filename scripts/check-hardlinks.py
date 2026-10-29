"""Compare internal hardlink equivalence classes without following symlinks."""

import argparse
import json
import os
from pathlib import Path
import stat


def groups(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("hardlink root must be an ordinary directory")
    inodes = {}
    for parent, _directories, files in os.walk(root, followlinks=False):
        for name in files:
            path = Path(parent) / name
            metadata = path.lstat()
            if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
                inodes.setdefault((metadata.st_dev, metadata.st_ino), []).append(path.relative_to(root).as_posix())
    return {tuple(sorted(paths)) for paths in inodes.values() if len(paths) > 1}


def compare(staged, final):
    expected, actual = groups(staged), groups(final)
    if expected != actual:
        missing = [paths[:8] for paths in sorted(expected - actual)[:3]]
        extra = [paths[:8] for paths in sorted(actual - expected)[:3]]
        raise ValueError(f"final rootfs hardlink topology differs: missing={missing!r}, extra={extra!r}")
    return {"hardlink_groups": len(expected), "exact_internal_topology": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    arguments = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("full rootfs verification runs only on GitHub")
    temporary = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    for root in (arguments.staged, arguments.final):
        if root.resolve() == temporary or not root.resolve().is_relative_to(temporary):
            parser.error("rootfs verification requires disposable RUNNER_TEMP roots")
    print(json.dumps(compare(arguments.staged, arguments.final), indent=2))
