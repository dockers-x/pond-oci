#!/usr/bin/env bash
set -euo pipefail

repository="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -ne 0 ]; then
  printf 'Usage: %s (configure KIT_SOURCE, ROOTFS_FETCH or OCI_OUTPUT through the environment)\n' "$0" >&2
  exit 2
fi
kit_source="${KIT_SOURCE:-$repository/../oci-kit}"
if ! command -v docker >/dev/null 2>&1 || ! docker buildx version >/dev/null 2>&1; then
  printf 'Docker with Buildx is required; this script never installs or starts a daemon.\n' >&2
  exit 1
fi
if [ ! -f "$kit_source/crates/lighos-init/Cargo.toml" ]; then
  printf 'Set KIT_SOURCE to a ca-x/oci-kit checkout.\n' >&2
  exit 1
fi
bash "$repository/scripts/fetch-rootfs.sh" --locked
digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$repository/rootfs.lock.json")"
kit_revision=development
if git -C "$kit_source" rev-parse --verify HEAD >/dev/null 2>&1 && [ -z "$(git -C "$kit_source" status --porcelain)" ]; then
  kit_revision="$(git -C "$kit_source" rev-parse HEAD)"
fi
mkdir -p "$repository/.build"
docker buildx build \
  --platform linux/amd64 \
  --build-context "oci-kit=$kit_source" \
  --build-context "rootfs=$repository/.cache/$digest" \
  --build-arg "ROOTFS_SHA256=$digest" \
  --build-arg "OCI_KIT_REVISION=$kit_revision" \
  --tag "${IMAGE_TAG:-pond-lightos:development}" \
  --output "type=oci,dest=${OCI_OUTPUT:-$repository/.build/pond-lightos.oci.tar}" \
  "$repository"
