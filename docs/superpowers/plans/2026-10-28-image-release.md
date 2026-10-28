# Verified amd64 OCI release implementation plan

> **For agentic workers:** Use executing-plans task by task. Observe meaningful
> regression failures in GitHub Actions before correcting production behavior.

**Goal:** Build one audited amd64 Pond OCI artifact on GitHub and publish matching
SemVer releases to Docker Hub and GHCR.

**Architecture:** Keep upstream resolution, version policy, Dockerfile and
registry publication in this recipe. Use the accepted Rust toolkit for generic
processing and LightOS adaptation; platform credentials stay platform-owned.

**Tech Stack:** GitHub Actions, Rust toolkit, Python standard library, BuildKit,
OCI archive and registry copy tooling available only on the runner.

**Spec:** `docs/image-acceptance.md`.

## Global constraints

- Downloads, builds and executable acceptance only on GitHub; local source work
  and SSH source publication only. Linux amd64 only.
- Do not disclose credentials or mutate this host's services/accounts/disks.
- Preserve the distinction between image publication and physical desktop boot.
- Independent read-only review before release; commit/push completed stages.

## Review focus

- Partial mask failures or a list without a final newline must not escape checks.
- An upstream update must not silently replace the reviewed rootfs lock.
- Hash-only upstream content must not masquerade as a downstream SemVer.
- A release tag/version mismatch or an existing registry tag must stop publishing.
- Final-layer metadata loss must not be hidden by a successful extraction step.

## Tasks

1. [x] Reproduce the two mask cases and unlocked workflow in remote source CI,
   then fix the production loop and locked download. The test-first commit
   intentionally exposes those failures before the correction commit.
2. [ ] Add `image.toml` and `scripts/image-metadata.py` with process tests for
   version syntax, exact tag matching, locked commits and development identity.
   Feed the resulting version/revision into image labels and build inputs.
3. [ ] Reopen the Rust adapter gate for desktop integration. Read the prior
   ponzS/Claude findings and audit the locked Niri payload in Actions. Implement
   device/VT/session support in `lighos-init` with remote process tests and fresh
   review before resuming packaging. Desktop-only, no headless fallback.
4. [ ] Check the final OCI artifact on the runner, with small fixture tests for
   invalid config, missing masks/cleanup and changed retained metadata.
5. [ ] Wire tag-only publication of that verified archive to both registries,
   preserving digests and refusing existing version tags. Validate the actual
   amd64 image and registry results without downloading them to this host.
6. [ ] Obtain fresh whole-change review, resolve important findings, record
   remote verification and publish the initial experimental SemVer release.

## Rulings and progress

- Reuse the authorized `main` checkouts; no branch/worktree or concurrent writer
  is needed. All behavior tests run in Actions, including red-to-green evidence.
- User explicitly authorizes Docker Hub and GHCR publication, superseding the
  earlier source-only/no-image-publication boundary. Initial image remains
  experimental, but must include the Niri desktop integration. Headless was
  explicitly rejected and is not a fallback deliverable.
- Toolkit gate passed at `cbf327f`; first OCI construction run `40663605078`
  succeeded at recipe `8d25833`. That run has no final-layer or boot assertions.
- Source regression run `40666844536` observed the three intended failures;
  correction `bd02679` passed all 13 tests in run `40667293537`.
- Metadata process tests at `77911aa` failed in run `40667512586` because the new
  CLI did not yet exist. Implementation and its green remote evidence follow.
- Metadata implementation `33226a0` passed source run `40669441987`. Desktop
  audit run `40669733311` succeeded: the real entry is `niri-session`, which
  starts the user `niri.service` (`niri --session`); runuser-l includes
  system-login/pam_systemd. This is payload evidence, not a boot result.
- User authorizes extending `lighos-init` and modifying/releasing upstream
  lightos-remote-desktop/AUR when needed. Investigating explicit package staging
  first: ordinary AUR hooks generate auth and activate a Cage/Hyprland owner,
  which cannot run in an image build or substitute for Pond/Niri.
