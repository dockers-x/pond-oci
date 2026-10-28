# Image build and release contract

- All rootfs/dependency downloads, builds and executable acceptance run in
  GitHub Actions. Local work edits/reviews source, pushes over SSH and reads
  workflow status/logs. Do not download rootfs or image artifacts locally.
- Build and publish only `linux/amd64`. There is no ARM matrix, QEMU or claim
  that the x86-64 upstream artifact supports another architecture.
- Normal builds consume the committed `rootfs.lock.json` without refreshing it.
  Latest discovery remains a separate explicit update step; review a changed
  hash before publishing an image made from it. Never execute upstream Python.
- The image has its own SemVer, initially `0.1.0`; the upstream SHA-256 is
  provenance, not a version. `image.toml` fixes the planned version and toolkit
  commit. A formal `vX.Y.Z` tag must match that version exactly. Untagged builds
  use a development prerelease, never the formal version tag.
- A published version fixes rootfs hash, toolkit commit and recipe commit.
  Do not overwrite an existing version tag. Rootfs-only updates normally bump
  PATCH; compatible features bump MINOR and breaking contracts bump MAJOR.
  Pre-1.0 builds remain explicitly experimental.
- Publish the same verified OCI artifact to Docker Hub and GHCR. Reuse
  `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `DOCKER_IMAGE` variable/secret and
  `GITHUB_TOKEN` conventions from `dockers-x/rustdesk-server`'s `forapi` workflow.
  Registry credentials never enter rootfs, build arguments or source files.
- Before publication, inspect the final OCI config/layer: amd64, systemd CMD,
  stop signal, version/source labels, service masks, default target, cleanup,
  installed hook and retained rootfs metadata. Do not execute rootfs programs
  during this static artifact check. Report what was actually checked.
- OCI construction/publication does not prove real LightOS seed/account/SSH,
  GPG-update or Niri/VT/PAM/logind startup. Keep those acceptance limits visible.

Commands initiated locally only dispatch or inspect GitHub workflows. Tests,
tool compilation, rootfs fetching and image construction commands in other
documents are runner-side operations, not local execution instructions.
