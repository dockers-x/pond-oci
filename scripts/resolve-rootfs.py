#!/usr/bin/env python3
"""Resolve Pond's installer declaration without executing upstream Python."""

import argparse
import ast
import base64
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

REPOSITORY = "bflycomputer/iso-installer"
DECLARATION_PATH = "src/backend/model.py"
API_BASE = "https://api.github.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def declaration(source):
    assignments = {}
    for statement in ast.parse(source).body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if isinstance(target, ast.Name) and target.id in ("ROOTFS_SHA256", "ROOTFS_URL"):
            if target.id in assignments:
                raise ValueError(f"Duplicate declaration: {target.id}")
            assignments[target.id] = statement.value

    digest_node = assignments.get("ROOTFS_SHA256")
    if not isinstance(digest_node, ast.Constant) or not isinstance(digest_node.value, str):
        raise ValueError("Expected a literal ROOTFS_SHA256")
    digest = digest_node.value
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid upstream SHA-256")

    url_node = assignments.get("ROOTFS_URL")
    if isinstance(url_node, ast.Constant) and isinstance(url_node.value, str):
        url = url_node.value
    elif isinstance(url_node, ast.JoinedStr):
        parts = []
        for part in url_node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
            elif (
                isinstance(part, ast.FormattedValue)
                and isinstance(part.value, ast.Name)
                and part.value.id == "ROOTFS_SHA256"
                and part.conversion == -1
                and part.format_spec is None
            ):
                parts.append(digest)
            else:
                raise ValueError("Unsupported ROOTFS_URL expression")
        url = "".join(parts)
    else:
        raise ValueError("Expected a literal URL or simple digest interpolation")

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "releases.butterfly.so"
        or parsed.path != f"/rootfs/{digest}/pond-rootfs.tar.zst"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Unexpected Pond release URL; review upstream changes")
    return url, digest


def api(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "pond-oci-rootfs-resolver",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    suffix = f"/{path}" if path else ""
    request = Request(f"{API_BASE}/repos/{REPOSITORY}{suffix}", headers=headers)
    with urlopen(request, timeout=45) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Upstream response exceeds resolver limit")
    return json.loads(data)


def resolve(fetch=api):
    branch = fetch("")["default_branch"]
    if not isinstance(branch, str) or not branch:
        raise ValueError("Missing default branch")
    revision = fetch(f"commits/{quote(branch, safe='')}")["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid source revision")
    document = fetch(f"contents/{DECLARATION_PATH}?ref={revision}")
    if document.get("type") != "file" or document.get("encoding") != "base64":
        raise ValueError("Expected a base64 source file")
    encoded = "".join(document["content"].split())
    source = base64.b64decode(encoded, validate=True).decode("utf-8")
    url, digest = declaration(source)
    return {
        "schema_version": 1,
        "url": url,
        "sha256": digest,
        "metadata": {
            "upstream_repository": f"https://github.com/{REPOSITORY}",
            "upstream_revision": revision,
            "upstream_path": DECLARATION_PATH,
        },
    }


def update(output, source, check=False):
    if output.exists():
        previous = json.loads(output.read_text())
        if all(previous.get(key) == source[key] for key in ("schema_version", "url", "sha256")):
            return False
    if not check:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(source, temporary, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.replace(output)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent.parent / "rootfs.lock.json")
    parser.add_argument("--check", action="store_true", help="Exit 1 when the rootfs changed; do not write")
    args = parser.parse_args()
    source = resolve()
    changed = update(args.output, source, args.check)
    print(f"{'changed' if changed else 'unchanged'} rootfs: {source['sha256']}")
    return int(args.check and changed)


if __name__ == "__main__":
    raise SystemExit(main())
