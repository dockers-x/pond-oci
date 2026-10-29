#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_SERVER_URL:-}" == https://github.com && -z "${ACT:-}" ]]
[[ $EUID == 0 && $# == 1 && "${GITHUB_RUN_ID:?}" =~ ^[0-9]+$ ]]
image="$1"
[[ "$image" == "pond-systemd-ci:$GITHUB_RUN_ID" ]]
repository="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="$(mktemp -d "${RUNNER_TEMP:?}/pond-systemd.XXXXXX")"
report="$RUNNER_TEMP/pond-systemd-report"
mkdir -p "$report"
container_id=''
case_name=''

collect() {
  [[ -n "$container_id" ]] || return 0
  docker logs --tail 120 "$container_id" > "$report/$case_name-console.log" 2>&1 || true
  timeout 20 docker exec "$container_id" journalctl -b --no-pager -n 200 \
    > "$report/$case_name-journal.log" 2>&1 || true
  timeout 10 docker exec "$container_id" systemctl --failed --no-pager \
    > "$report/$case_name-failed-units.log" 2>&1 || true
}

finish() {
  status=$?
  trap - EXIT
  collect
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null || true
  fi
  exit "$status"
}
trap finish EXIT

for case_name in seeded unseeded; do
  container_id="$(docker create --name "pond-systemd-$GITHUB_RUN_ID-$case_name" \
    --privileged --cgroupns=private --network=none \
    --tmpfs /run:rw,nosuid,nodev,mode=755 --tmpfs /run/lock:rw,nosuid,nodev,mode=755 \
    --env container=docker --env GITHUB_ACTIONS=true "$image")"
  [[ "$container_id" =~ ^[0-9a-f]{64}$ ]]
  install -m 0755 "$repository/tests/fixtures/pond-ci-platform-setup.sh" "$workspace/pond-ci-platform-setup"
  printf 'synthetic GitHub boot fixture\n' > "$workspace/pond-systemd-ci"
  docker cp "$workspace/pond-ci-platform-setup" "$container_id:/usr/local/bin/pond-ci-platform-setup"
  docker cp "$workspace/pond-systemd-ci" "$container_id:/etc/pond-systemd-ci"
  docker cp "$repository/tests/fixtures/lightos-setup.service" "$container_id:/etc/systemd/system/lightos-setup.service"
  if [[ "$case_name" == seeded ]]; then
    printf '%s\n' LIGHTOS_USERNAME=pond-seeded LIGHTOS_PASSWORD=synthetic-ci-only \
      LIGHTOS_CI_UID=1207 LIGHTOS_CI_HOME=/home/pond-alternate-home > "$workspace/seed.env"
    chmod 0600 "$workspace/seed.env"
    docker cp "$workspace/seed.env" "$container_id:/etc/lightos/seed.env"
  fi
  docker start "$container_id" >/dev/null
  deadline=$((SECONDS + 360))
  while ! timeout 10 docker exec "$container_id" systemctl is-active --quiet multi-user.target; do
    [[ "$(docker inspect --format '{{.State.Running}}' "$container_id")" == true && $SECONDS -lt $deadline ]]
    sleep 3
  done
  [[ "$(docker exec "$container_id" readlink /proc/1/exe)" == /usr/lib/systemd/systemd ]]
  if [[ "$case_name" == seeded ]]; then
    for service in lightos-setup.service lighos-init.service; do
      [[ "$(docker exec "$container_id" systemctl show --property=ActiveState --value "$service")" == active ]]
      [[ "$(docker exec "$container_id" systemctl show --property=Result --value "$service")" == success ]]
    done
    docker exec "$container_id" test -f /var/lib/lightos/initialized
    docker exec "$container_id" test -f /var/lib/oci-kit/lightos-init.json
    docker exec "$container_id" test ! -e /etc/lightos/seed.env
    [[ "$(docker exec "$container_id" id -u pond-seeded)" == 1207 ]]
    [[ "$(docker exec "$container_id" stat -c %u /home/pond-alternate-home)" == 1207 ]]
    docker exec "$container_id" test -f /home/pond-alternate-home/.config/niri/config.kdl
    docker exec "$container_id" systemctl restart lighos-init.service
    docker exec "$container_id" journalctl --sync
    docker exec "$container_id" journalctl -u lighos-init.service --no-pager -o cat > "$report/initializer.log"
    python3 - "$report/initializer.log" <<'PY'
import json
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()
decoder = json.JSONDecoder()
documents = [decoder.raw_decode(text[match.start():])[0] for match in re.finditer(r'(?m)^\{', text)]
assert [document['changed'] for document in documents] == [True, False], documents
PY
    docker exec "$container_id" systemctl --failed --plain --no-legend --no-pager > "$report/seeded-failed-units.log"
    if [[ -s "$report/seeded-failed-units.log" ]]; then
      cat "$report/seeded-failed-units.log"
      printf 'Seeded boot must not leave failed system units.\n' >&2
      exit 1
    fi
  else
    [[ "$(docker exec "$container_id" systemctl show --property=AssertResult --value lighos-init.service)" == no ]]
    docker exec "$container_id" test ! -e /var/lib/lightos/initialized
    docker exec "$container_id" test ! -e /var/lib/oci-kit/lightos-init.json
  fi
  for service in lightos-remote-desktop.service lightos-remote-desktop-session.service; do
    [[ "$(docker exec "$container_id" systemctl show --property=ActiveState --value "$service")" == inactive ]]
  done
  docker exec "$container_id" test ! -e /etc/lightos/remote-desktop.env
  printf '%s: actual systemd boot and adapter contract accepted\n' "$case_name"
  collect
  docker stop --time 20 "$container_id" >/dev/null
  docker rm "$container_id" >/dev/null
  container_id=''
done
printf '%s\n' '{"scope":"actual OCI systemd boot with synthetic platform setup, not LightOS proxy","seeded":true,"missing_seed_rejected":true,"initializer_idempotent":true,"remote_not_activated":true}' \
  > "$report/evidence.json"
cat "$report/evidence.json"
