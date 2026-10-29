#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_SERVER_URL:-}" == https://github.com && -z "${ACT:-}" ]]
[[ $EUID == 0 && "$(uname -m)" == x86_64 ]]
repository="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(realpath -e -- "${RUNNER_TEMP:?}")"
root="$temporary/pond-image-root"
[[ ! -e "$root" && ! -L "$root" ]]
[[ "${ROOTFS_SHA256:?}" =~ ^[0-9a-f]{64}$ ]]
tools="${KIT_BINARIES:?}"
binary="${REMOTED_BINARY:?}"
report="$temporary/pond-image-report"
install -d -m 0755 "$root" "$report"
bsdtar --numeric-owner --acls --xattrs -xpf "$repository/.cache/$ROOTFS_SHA256/pond-rootfs.tar.zst" -C "$root"
"$tools/rootfs-cleaner" mark --root "$root"
"$tools/lighos-init" prepare-keyrings --root "$root" --config "$repository/profiles/lightos.toml" --apply
bwrap --unshare-pid --unshare-ipc --unshare-uts --hostname pond-image-build \
  --die-with-parent --bind "$root" / --proc /proc --dev /dev \
  --perms 1777 --tmpfs /dev/shm --dir /run/systemd/resolve \
  --ro-bind /etc/resolv.conf /run/systemd/resolve/stub-resolv.conf --clearenv \
  --setenv PATH /usr/bin:/bin --setenv LANG C.UTF-8 \
  /usr/bin/pacman -Syu --noconfirm --needed cage
bwrap --unshare-pid --unshare-ipc --unshare-net --unshare-uts \
  --die-with-parent --bind "$root" / --proc /proc --dev /dev --clearenv \
  --setenv PATH /usr/bin:/bin --setenv LANG C.UTF-8 \
  /usr/bin/pacman -Q > "$report/packages.txt"
"$tools/rootfs-cleaner" clean --root "$root" --policy "$repository/profiles/cleanup.toml" --apply
"$binary" install-service --stage-only --test-root "$root"
"$tools/lighos-init" install --root "$root" --config "$repository/profiles/lightos.toml"
install -d -m 0755 "$root/etc/lightos"
printf 'LIGHTOS_REMOTE_DESKTOP_COMPOSITOR=niri\n' > "$root/etc/lightos/remote-desktop-native.env"
chmod 0644 "$root/etc/lightos/remote-desktop-native.env"
while IFS= read -r unit || [[ -n "$unit" ]]; do
  case "$unit" in ''|*[!A-Za-z0-9@_.-]*|..*) exit 2 ;; esac
  ln -sfnT /dev/null "$root/etc/systemd/system/$unit"
done < "$repository/profiles/masked-units.txt"
ln -sfnT /usr/lib/systemd/system/multi-user.target "$root/etc/systemd/system/default.target"
for forbidden in etc/lightos/seed.env etc/lightos/remote-desktop.env var/lib/lightos/initialized var/lib/oci-kit etc/machine-id etc/pacman.d/gnupg home/pond-ci; do
  [[ ! -e "$root/$forbidden" && ! -L "$root/$forbidden" ]]
done
[[ -x "$root/usr/lib/systemd/systemd" && -x "$root/usr/local/bin/lighos-init" && -x "$root/usr/lib/lightos-remoted/lightos-remoted" ]]
[[ -f "$root/usr/lib/systemd/system/lightos-remote-desktop.service" && -f "$root/usr/lib/systemd/system/lightos-remote-desktop-session.service" ]]
rm -- "$root/.oci-kit-staging"
