#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_SERVER_URL:-}" == https://github.com && -z "${ACT:-}" ]]
[[ $EUID == 0 && $# == 3 ]]
temporary="$(realpath -e -- "${RUNNER_TEMP:?}")"
root="$(realpath -e -- "$1")"
layout="$2"
output="$3"
[[ ! -L "$1" && -d "$root" && "$root" == "$temporary/"* ]]
[[ "$layout" == "$temporary/"* && "$output" == "$temporary/"* ]]
[[ ! -e "$layout" && ! -L "$layout" && ! -e "$output" && ! -L "$output" ]]
archive="$(mktemp "$temporary/pond-layer.XXXXXX.tar")"
trap 'rm -f -- "$archive"' EXIT
tar --format=pax --numeric-owner --xattrs --xattrs-include='*' --acls \
  -cpf "$archive" -C "$root" .
expected="$(sha256sum "$archive" | cut -d ' ' -f1)"
umoci init --layout "$layout"
umoci new --image "$layout:candidate"
umoci raw add-layer --image "$layout:candidate" "$archive"
umoci config --image "$layout:candidate" --architecture amd64 --os linux \
  --clear=config.env --clear=config.cmd \
  --config.env LANG=C.UTF-8 --config.cmd /sbin/init --config.stopsignal SIGRTMIN+3 \
  --config.label 'org.opencontainers.image.title=Pond Desktop for LightOS (experimental)' \
  --config.label 'org.opencontainers.image.source=https://github.com/dockers-x/pond-oci' \
  --config.label "org.opencontainers.image.version=${IMAGE_VERSION:?}" \
  --config.label "org.opencontainers.image.revision=${RECIPE_REVISION:?}" \
  --config.label "so.butterfly.rootfs.sha256=${ROOTFS_SHA256:?}" \
  --config.label "eu.ca-x.oci-kit.revision=${KIT_REVISION:?}" \
  --config.label "eu.ca-x.lightos-remoted.revision=${REMOTED_REVISION:?}"
manifest="$(jq -er '.manifests | select(length == 1) | .[0].digest | split(":")[1]' "$layout/index.json")"
config="$(jq -er '.config.digest | split(":")[1]' "$layout/blobs/sha256/$manifest")"
jq -e --arg expected "sha256:$expected" '.rootfs.diff_ids == [$expected]' "$layout/blobs/sha256/$config"
skopeo copy --preserve-digests "oci:$layout:candidate" "oci-archive:$output"
chmod 0644 "$output"
printf 'Original tar preserved as OCI diff_id sha256:%s\n' "$expected"
