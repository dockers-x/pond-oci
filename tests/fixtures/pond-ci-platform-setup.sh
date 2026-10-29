#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_ACTIONS:-}" == true && -f /etc/pond-systemd-ci ]]
[[ ! -f /var/lib/lightos/initialized ]] || exit 0
install -d -m 0755 /var/lib/lightos
install -d -m 0700 /etc/pacman.d/gnupg
pacman-key --init
pacman-key --populate archlinux
useradd --create-home --user-group --uid "${LIGHTOS_CI_UID:?}" \
  --home-dir "${LIGHTOS_CI_HOME:?}" --shell /usr/bin/bash "${LIGHTOS_USERNAME:?}"
for group in sudo wheel; do
  getent group "$group" >/dev/null || groupadd "$group"
done
usermod -aG wheel,sudo,audio "$LIGHTOS_USERNAME"
printf '%s:%s\n' "$LIGHTOS_USERNAME" "${LIGHTOS_PASSWORD:?}" | chpasswd -c SHA512
rm -- /etc/lightos/seed.env
printf 'synthetic GitHub platform prerequisite, not the LightOS implementation\n' > /var/lib/lightos/initialized
