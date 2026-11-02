#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value, length):
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def metadata(root, revision, release_tag, kit_override, version_override=""):
    image = tomllib.loads((root / "image.toml").read_text())
    require({"schema_version", "version", "kit_revision"} <= set(image) <= {"schema_version", "version", "kit_revision", "remoted_revision"}, "invalid image metadata fields")
    require(type(image["schema_version"]) is int and image["schema_version"] == 1, "unsupported image schema")
    version = image["version"]
    require(isinstance(version, str) and VERSION.fullmatch(version), "image version must be MAJOR.MINOR.PATCH without leading zeros")
    require(identifier(revision, 40), "recipe revision must be an exact 40-character commit")
    kit_revision = image["kit_revision"]
    require(identifier(kit_revision, 40), "kit revision must be an exact 40-character commit")
    require(not kit_override or kit_override == kit_revision, "kit revision override does not match image.toml")
    require(not release_tag or release_tag == f"v{version}", "release tag must exactly match image.toml as vMAJOR.MINOR.PATCH")
    source = json.loads((root / "rootfs.lock.json").read_text())
    require(isinstance(source, dict) and type(source.get("schema_version")) is int and source["schema_version"] == 1, "unsupported rootfs source schema")
    require(identifier(source.get("sha256"), 64), "rootfs digest must be a complete SHA-256")
    result = {
        "schema_version": 1,
        "base_version": version,
        "version": version if release_tag else f"{version}-dev.g{revision[:12]}",
        "release": bool(release_tag),
        "recipe_revision": revision,
        "kit_revision": kit_revision,
        "rootfs_sha256": source["sha256"],
    }
    if version_override:
        require(not release_tag and re.fullmatch(VERSION.pattern + r"-rc\.[1-9][0-9]*", version_override), "invalid automatic RC version")
        result["version"] = version_override
    if "remoted_revision" in image:
        require(identifier(image["remoted_revision"], 40), "invalid remoted revision")
        result["remoted_revision"] = image["remoted_revision"]
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate the image's downstream SemVer and locked source identities")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--kit-revision", default="")
    parser.add_argument("--image-version", default="")
    parser.add_argument("--format", choices=("json", "github"), default="json")
    arguments = parser.parse_args()
    try:
        result = metadata(arguments.root, arguments.revision, arguments.release_tag, arguments.kit_revision, arguments.image_version)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    if arguments.format == "github":
        for name, value in result.items():
            print(f"{name}={str(value).lower() if isinstance(value, bool) else value}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
