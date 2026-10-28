# Work log

## 2026-10-28 — Pond source and headless OCI recipe

- Kept distribution-specific logic here: upstream release discovery, exact
  cleanup paths, LightOS profile and service masks are not generic kit defaults.
- Resolved the upstream default branch to a commit before reading its rootfs
  declarations. Parsed a restricted AST without importing or executing upstream
  installer code; locked the artifact URL, SHA-256 and source provenance.
- Downloaded 2,638,674,881 bytes with `rootfs-fetch`, verified the declared SHA-256
  on download and cache reuse, and audited the actual tar without execution.
  `docs/rootfs-audit.md` records package, init, account and session observations.
- Preserved `/etc/skel`, package databases and unverified kernel/firmware/Nix/
  Flatpak dependencies. Cleanup targets known instance identity and cache paths;
  the recipe does not pretend file deletion is package removal.
- Added a multi-stage Dockerfile that compiles kit tools for musl, extracts into
  offline staging and copies only the processed tree into the final scratch
  image. The default is headless, not a validated physical desktop session.
- Added ten Python behavior tests and shell syntax checks; all pass locally.
  Rechecked the latest upstream declaration: the locked artifact is unchanged.
- Ran release CLI smoke against a disposable directory: two offline adapter
  installs, cleanup dry-run and explicit deletion preserve the retained file.
- Local Docker/Buildx is unavailable. The build script fails explicitly rather
  than installing or starting a host daemon. Remote build and runtime results
  must be recorded separately; no rootfs or image is publicly uploaded.
- Final source checks pass: ten Python tests, both shell syntax checks and the
  release adapter's default dry-run. Toolkit source is locally committed as
  `2ef0ba1`; authenticated Git HTTPS publishing currently times out, so a local
  commit must not be confused with a successful push or a remote CI run.

The user requests `ub-mode` and a commit/push after each verified phase.
Source publishing is not proof of OCI construction, redistribution rights or
successful LightOS account/keyring/Niri/VT/PAM/logind startup.

## 2026-10-28 — CLI gate and GitHub-only image execution

- The toolkit completion gate passed before starting image work: all three
  GitHub jobs succeeded at `cbf327f` in run `40662397249`, including minimum Rust,
  static binaries and isolated initializer runtime acceptance. An independent
  whole-change review found no remaining issue. The documentation head
  `daaf572` also passed run `40663154259`.
- Dispatched the first image workflow as run `40663605078`, recipe source
  `8d258334d047925e8e2d871df77293e3108eba9e`, exact kit source
  `cbf327f0fa20b4e87b491b14aeed373f20cf223b`. At this entry's writing, toolkit
  compilation and the verified rootfs download succeeded on GitHub; OCI
  construction is still running. No image/boot success is inferred.
- The user's new execution constraint places every subsequent rootfs/dependency
  download, build and runtime check in GitHub Actions. Local work is source
  editing/static review, SSH pushes and workflow/log inspection only. Updated
  README entry points accordingly; the generic toolkit remains platform-neutral.
- Existing workflows do not upload the rootfs or OCI archive or push a registry.
  An independent read-only recipe review is in progress. Real LightOS and Niri
  startup acceptance remain separate from the current OCI construction attempt.

## 2026-10-28 — Remote regression and release preparation

- First build run `40663605078` completed successfully in 11m27s on GitHub.
  This proves OCI construction only; it did not validate the final layer or boot.
- Independent static review confirmed two P2s: the workflow refreshes the rootfs
  lock before building, and the mask loop can hide an early failure or omit a
  final non-newline-terminated unit. Added three targeted regression tests of
  the production command/configuration; remote CI must demonstrate the failures
  before production is corrected. No local executable tests or builds are run.
- User adds independent SemVer releases, Docker Hub plus GHCR publication and
  amd64-only output. Existing registry secrets are already configured. Read the
  referenced rustdesk workflow's variable/secret names, without reading values.
  `docs/image-acceptance.md` and the image-release plan pin the revised contract.
- The explicit registry-publication request supersedes the earlier no-image-
  upload policy. It does not establish a successful LightOS/Niri boot or an
  upstream version number; those claims remain excluded.
- GitHub source run `40666844536` at `5558750` reproduced exactly three intended
  failures out of 13 tests: unlocked fetch invocation, early mask failure
  incorrectly returning zero, and an unprocessed final unit without newline.
  Corrected the workflow to `--locked`, retained the final line and explicitly
  propagated every failed mask. The green follow-up must also run on GitHub.
- Added subprocess acceptance for the new image metadata CLI: development and
  release SemVer identities, exact tag match, locked rootfs/toolkit provenance,
  invalid identifiers and safe GitHub outputs. This test-first phase is sent to
  Actions before implementing the new CLI; no test runs on this host.

## 2026-10-28 — Source publication over SSH

- HTTPS attempts timed out; the final response also reported that the OAuth token
  lacks the scope required for workflow-file pushes. The user requests SSH.
- Existing SSH configuration authenticates as `czyt` through `ssh.github.com:443`.
  Changed origin to `git@github.com:dockers-x/pond-oci.git` and successfully pushed
  initial source commit `8dac799` to `main`, with `origin/main` tracking configured.
- No rootfs, cache, image or user credentials are in the pushed source. Runtime
  and OCI construction are still pending and are not inferred from push success.
