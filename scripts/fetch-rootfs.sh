#!/usr/bin/env bash
set -euo pipefail

repository="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
locked=0
if [ "${1:-}" = --locked ]; then
  locked=1
  shift
fi
if [ "$#" -ne 0 ]; then
  printf 'Usage: %s [--locked]\n' "$0" >&2
  exit 2
fi
if [ "$locked" -eq 0 ]; then
  python3 "$repository/scripts/resolve-rootfs.py"
fi
digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$repository/rootfs.lock.json")"
output="$repository/.cache/$digest/pond-rootfs.tar.zst"
"${ROOTFS_FETCH:-rootfs-fetch}" --source "$repository/rootfs.lock.json" --output "$output"
