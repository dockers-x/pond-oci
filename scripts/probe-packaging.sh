#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_SERVER_URL:-}" == https://github.com && -z "${ACT:-}" ]]
[[ $EUID == 0 ]]
repository="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="$(mktemp -d "${RUNNER_TEMP:?}/pond-metadata.XXXXXX")"
root="$workspace/root"
mkdir -p "$root/owned" "$root/acl" "$workspace/extracted"
chmod 0751 "$root"
setfacl -m u:1234:r-x,d:u:1234:r-x "$root/acl"
printf 'preserved payload\n' > "$root/owned/payload"
chown 1234:2345 "$root/owned" "$root/owned/payload"
chmod 2750 "$root/owned"
chmod 6750 "$root/owned/payload"
ln "$root/owned/payload" "$root/owned/alias"
ln -s /owned/payload "$root/absolute-link"
printf 'capability payload\n' > "$root/capability"
setcap cap_net_bind_service=ep "$root/capability"
IMAGE_VERSION=0.0.0-test RECIPE_REVISION=fixture ROOTFS_SHA256=fixture \
  KIT_REVISION=fixture REMOTED_REVISION=fixture \
  bash "$repository/scripts/package-desktop.sh" "$root" "$workspace/packed" "$workspace/image.tar"
mkdir "$workspace/layout"
tar -xf "$workspace/image.tar" -C "$workspace/layout"
manifest="$(jq -er '.manifests | select(length == 1) | .[0].digest | split(":")[1]' "$workspace/layout/index.json")"
layer="$(jq -er '.layers | select(length == 1) | .[0].digest | split(":")[1]' "$workspace/layout/blobs/sha256/$manifest")"
bsdtar --numeric-owner --xattrs --acls -xpf "$workspace/layout/blobs/sha256/$layer" -C "$workspace/extracted"
for path in . acl owned owned/payload owned/alias capability absolute-link; do
  expected="$(stat -c '%u:%g:%a' "$root/$path")"
  actual="$(stat -c '%u:%g:%a' "$workspace/extracted/$path")"
  printf '%s expected=%s actual=%s\n' "$path" "$expected" "$actual"
  [[ "$expected" == "$actual" ]]
done
[[ "$(stat -c '%i' "$workspace/extracted/owned/payload")" == "$(stat -c '%i' "$workspace/extracted/owned/alias")" ]]
[[ "$(readlink "$workspace/extracted/absolute-link")" == /owned/payload ]]
[[ "$(getfattr --only-values -n security.capability "$root/capability" | base64 -w0)" == "$(getfattr --only-values -n security.capability "$workspace/extracted/capability" | base64 -w0)" ]]
cmp "$root/owned/payload" "$workspace/extracted/owned/payload"
diff -u <(getfacl -ncp "$root/acl") <(getfacl -ncp "$workspace/extracted/acl")
printf 'Actual desktop recipe preserved root mode, numeric ownership, ACLs, modes, links, capabilities and payload.\n'
