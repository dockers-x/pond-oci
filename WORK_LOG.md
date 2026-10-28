# Work log

## 2026-10-28 — Resume recipe-to-toolkit desktop ordering

- Ruling: native remoted-owner research stays deferred. Resume the existing
  toolkit/Pond plan without restoring the old headless image build.
- The accepted toolkit supports post-setup ordering, but this recipe still
  locks the earlier toolkit and omits both canonical desktop services from its
  initialization profile. Wire the existing Rust capability before new features.
- Add a real command-line regression: GitHub builds the recipe's locked toolkit,
  marks an isolated rootfs with rootfs-cleaner, then installs the actual Pond
  profile twice with lighos-init. Require both ordering drop-ins, preserved
  package units/opaque platform settings, no activation and no runtime marker.
- Strengthen the source profile contract before changing the profile or toolkit
  lock. RED must be observed remotely; no image/rootfs download, local toolkit
  build, host service operation or successful desktop boot is implied.

## 2026-10-28 — Preserve the native Pond shell, not just its compositor

- Source validation `40676461617` passed after the development-SemVer fix.
- The previous audit's top-level Niri config includes shell/config.kdl plus
  cfg/autostart.kdl. Its shell directory is an absolute link to
  `/usr/share/pond-interface/config/niri/shell`; inspecting only config.kdl
  cannot establish that the actual Pond shell/autostart is preserved.
- Extend only the read-only GitHub audit to include these regular KDL files
  and skel user units, with a 64-file/256-KiB text budget. Do not follow the
  archived symlink or execute payload programs. This is not image packaging.
- Upstream Niri v26.04 source exposes a Winit nested backend selected by an
  existing display; its headless backend is internal test infrastructure, not
  a public CLI mode. `--session` deliberately removes parent display variables.
  A prospective no-VT remote adapter must not use it for nested startup or
  silently replace Niri/Pond with the existing Hyprland owner. Runtime capture,
  input, shell and persistent-session tests remain required.
- Audit `40683134808` succeeded: the preserved shell config actually launches
  `qs -c pond-shell`; skel's personal autostart contains only a commented example.
  Record the native desktop boundary and remaining gates in
  `docs/desktop-adaptation.md`. Correct acceptance wording so physical VT is
  not incorrectly mandatory for a fully graphical remote instance.

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

## 2026-10-28 — Desktop-only scope correction

- User explicitly rejects headless, including an optional headless deliverable.
  The intended product is the Pond/Niri desktop. The original headless default
  was an implementation scoping mistake, not a user requirement. Suspend that
  workflow and all publication until the desktop adapter gate is satisfied.
- Source fix `bd02679` passed all 13 tests remotely in run `40667293537`.
  The SemVer process tests observed the absent metadata CLI in run `40667512586`;
  implement it without publishing a tag or image, and verify only in Actions.
- Retrieved the original Claude thread `ext-claude-raj37m` and re-read the
  first-principles/ponzS research. Its useful desktop mechanisms are allocated
  VT waiting, controlling-terminal seatd, device numeric groups, runuser-l
  PAM/logind and user D-Bus. Hyprland/UWSM launch commands are not Niri commands.
- Read current unit states and Omarchy launcher source without modifying any
  host service or reading seed credentials. Listed non-template units are not
  running, but some are enabled/inactive rather than disabled or masked; the
  existing console unit is restarting, so it is not proof of a working desktop.
- Independent read-only service review agrees: retain host-isolation masks,
  replace autonomous SDDM/getty display control with a LightOS-specific session,
  verify the seat backend, and do not blindly enable Bluetooth or ananicy.

## 2026-10-28 — Desktop payload evidence and safe package preinstallation

- Source CI `40669441987` at `33226a0` passed. The payload audit
  `40669733311` also passed without executing target programs: Niri's desktop
  entry invokes niri-session, the user unit invokes niri --session, and PAM
  runuser-l includes system-login/pam_systemd. These checks do not prove a GUI.
- Read local remote-desktop source, then fast-forwarded that clean source
  checkout over SSH to actual remote main `b086a3f`/release v0.1.21. No binary
  or rootfs is downloaded here. Installed host v0.1.20 is not the newest release.
- Ordinary package hooks generate authentication and start the virtual owner.
  User explicitly permits improving/releasing that program and AUR. Its new
  test-first staging contract is tracked in that source repository; keep all
  executable verification on GitHub and preserve the existing service names.
- Extended this read-only workflow to record actual Pond dependency/FFmpeg
  SONAME metadata and actual AUR commits, and to read the pinned ponzS VT guard.
  No PKGBUILD, rootfs executable, native installer or package hook is executed.
  The desktop adapter gate stays open and no image publication is resumed.
- Independent metadata review found one P2: a numeric SHA prefix beginning with
  zero creates an invalid numeric SemVer prerelease identifier. Added a process
  regression for revision `012345678901` before changing version generation;
  source Actions must observe its failure and the correction remotely.
- Source run `40675303365` observed exactly that one failure out of 20 tests:
  `0.1.0-dev.012345678901` is invalid. Prefix every development commit identifier
  with `g`, preserving the original revision separately. Formal versions/tags
  do not change; a new Actions run must confirm the corrected behavior.
- ABI audit `40673977531` succeeded. The locked Pond rootfs contains Niri
  `26.04-1`, FFmpeg `2:9.0.2-2` providing libavcodec 63/libavutil 61/libswscale 10,
  Aquamarine 0.15.1, hyprutils SONAME 13 and libdisplay-info SONAME 3. These
  advertised ABIs match the currently published helper's requirements, not a
  guarantee that every future package or actual encoder works. Actual AUR heads
  remain 0.1.20 while upstream GitHub has v0.1.21; do not call them synchronized.
- Added a GitHub-only payload audit of the actual Niri desktop entry, session
  wrapper, user service, PAM and skel. It uses the accepted Rust fetch/inspect
  tools, does not execute rootfs programs and uploads no rootfs/image artifact.
- Reopen the CLI gate for new desktop support in `lighos-init` before resuming
  packaging, as required by the user's original ordering constraint. This is
  separate from SemVer/source validation and from real target display testing.

## 2026-10-28 — Source publication over SSH

- HTTPS attempts timed out; the final response also reported that the OAuth token
  lacks the scope required for workflow-file pushes. The user requests SSH.
- Existing SSH configuration authenticates as `czyt` through `ssh.github.com:443`.
  Changed origin to `git@github.com:dockers-x/pond-oci.git` and successfully pushed
  initial source commit `8dac799` to `main`, with `origin/main` tracking configured.
- No rootfs, cache, image or user credentials are in the pushed source. Runtime
  and OCI construction are still pending and are not inferred from push success.
