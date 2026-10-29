# Work log

## 2026-10-29 — Verify the packaging boundary, not only desktop rendering

- Candidate 154ba2b / 40824541717 succeeds: native desktop, fresh staging,
  actual amd64 OCI construction, config and selected final-layer gates all pass.
  This is an unpublished GitHub artifact, not a LightOS boot/proxy acceptance.
- Add a GitHub-only behavioral probe using the actual desktop Dockerfile and
  a tiny rootfs with non-root numeric owners, special modes, hardlinks, an
  absolute symlink and a security.capability xattr. The existing selected-path
  gate does not establish preservation of those properties. Run this probe
  before changing the packaging mechanism; do not download candidate artifacts.
- Actual recipe probe 40826215049 is behavioral RED after a successful build:
  `owned` changes from 1234:2345:2750 to 0:0:2750. Thus 40824541717 is not a
  release-quality artifact despite its selected-path gate passing. Replace the
  local-context COPY with numeric-owner pax tar + ADD, preserving archive
  ownership rather than flattening the rootfs to root. Re-run the same probe
  including hardlink identity and security.capability before another candidate.
- Metadata probe 64815ec / 40826409622 is GREEN, including the actual extracted
  capability bytes and hardlink inode identity. Add a full staged-root vs final
  layer read-only rsync checksum/owner/mode/link/ACL/xattr comparison to each
  candidate. Selected executables alone cannot prove the complete packaging
  boundary. Keep registry publication disabled until the other runtime gates.
- Add regression cases for an explicit verify-installed probe mode: require
  the reviewed binary's SHA-256 without replacing the final image binary,
  reject missing/different/symlink payloads, and retain the old staging guard.
  This is the next prerequisite for testing the actual unpacked OCI payload.
- Source RED 40827031657 confirms the verify-installed API does not yet exist.
  Implement hashing without copy/chmod in installed mode; normal staging still
  refuses replacement. Record the verified digest in final evidence. This alone
  is not final-image runtime acceptance; the workflow still needs to select it.
- Wire final-layer runtime testing after the full content comparison and before
  retaining the candidate. Mark only its disposable extraction, verify the
  installed remoted against the original same-run build digest, then run real
  Rust initialization twice and the native Pond/two-transport/frame gates.
  Preserve the signed Arch fixture's Pillow only under /run for test decoding;
  do not install test packages into the image or replace any image binary.
  This remains a namespace/synthetic-platform test, not systemd/LightOS proxy.
- Independent review finds rsync -H does not detect every extra hardlink at the
  destination. Add two-direction topology regression fixtures: preserve groups
  across different inode numbers, but reject both lost links and independent
  same-content files incorrectly coalesced. Compare path equivalence classes,
  not inode numbers across separate root directories.
- API-first regression 40827707248 fails because no topology checker exists.
  Add the checker and gate the real candidate before runtime mutation. Its
  equivalence classes ignore symlinks and compare relative path sets in both
  directions. Source tests cover extra coalescing as well as link splitting.
- Full candidate fab4975 / 40826727046 is RED: after successful ADD construction,
  root metadata and ACLs on run/tpm2-tss/eventlog and var/lib/tpm2-tss/system/
  keystore differ. Also correct root-owned report writes to sudo tee. Do not
  weaken the full comparison. Two builder transformations fail preservation:
  remove the transformation. Directly attach the original numeric-owner pax tar
  using umoci raw add-layer and require its original SHA-256 as the sole diff_id.
  Extend the tiny gate to root permissions and access/default ACLs. No registry
  release or final-runtime success is claimed before this passes on GitHub.
- Raw candidate 40829238410 preserves all observed file metadata and both ACLs,
  but full comparison rejects only the extraction root's mtime (`.d..t......`).
  Keep the gate strict and add a fixed old root mtime to the tiny behavioral
  probe to distinguish extraction metadata from a changed application payload.
  The final native runtime step has not yet run; no candidate is retained.
- Tiny fixed-time run 40830763626 reproduces the extraction-only RED:
  original root mtime 946684800 becomes 1793256128 while the original tar
  diff_id is intact and root permissions are preserved. Use GNU tar with
  numeric-owner, all xattrs and ACL restoration for the final test extraction,
  matching the source archive producer. Keep timestamps in the comparison;
  do not hide the difference with rsync -O or touch the destination afterwards.

## 2026-10-29 — Close the native Pond owner gate and stage an unpublished candidate

- Actual syscall evidence from 40819146213, inspected only on GitHub in
  40820205000, shows Cage shm_open of /dev/shm/wlroots-* returning EACCES.
  Give each disposable bwrap a new 1777 tmpfs there; never bind host shm.
  Fresh independent review finds no new P1/P2 in the mount change.
- 40820435244 then observes both original Pond layers, stable owner/Niri/qs
  identities across two transports and normal shutdown, but rejects the first
  uniform JPEG. Inspector 40821182287 confirms both first frames are one color.
- Socketpair regression RED 40821432580 reproduces premature first-frame
  acceptance. Decode candidates without lowering the external 256-color gate.
  Actual native GREEN 40821662911 yields two 1272x688, 1053-color JPEGs after
  three and one candidates respectively. Synthetic frame-ID tests cover ACK
  behavior; this fixture does not negotiate the server's sequenced flow mode.
- Review finds the two-second socket timeout can shorten the frame deadline.
  Delayed-frame RED 40822871259 reproduces that TimeoutError; ef68da1 carries
  one absolute deadline through partial header/body reads. Source/profile
  GREEN 40823095605 includes the delayed-frame regression.
- The candidate path re-extracts the original verified archive after disposing
  of the runtime fixture. It stages canonical units without activation/auth,
  selects Niri, applies the Rust kit and constructs an amd64 scratch image.
  Review catches the standalone installer's deliberate refusal of existing
  custom drop-ins: stage canonical remoted first, then install the Rust hook.
- Inspect the actual OCI config and single final tar layer on GitHub, using
  the reviewed Rust archive reader and virtual-root metadata checks for masks,
  executable ownership, native config links and absent instance state. This
  is not complete retained-xattr, LightOS boot/proxy, launcher, codec-worker
  or registry-release acceptance.

## 2026-10-29 — Separate native shell queries from launcher/app-start evidence

- Bounded independent read-only review confirms that the payload-audited
  Mod+Space binding invokes vicinae toggle, while sidebar.toggle only changes
  sidebar expansion. Existing IPC-query/frame success proves neither launcher
  selection nor application startup. Current upstream QML is not proof of the
  pinned payload's exported accessibility labels or welcome-dismiss behavior.
- Keep native-input acceptance explicit: dismiss the observed welcome layer,
  observe the real launcher, select an installed desktop entry and verify a
  new visible application window with matching process identity. Reject early
  spawn logs, command exit0 and screenshot-hash changes as success criteria.
- Update the resumed dependency boundary: remoted Niri configuration/doctor
  interface is accepted by 40787218608/2f43e31; private environment publishing
  is being implemented after missing-action RED 40790727648/52e2030. Persistent
  owner and desktop-image publishing remain unaccepted; no build is enabled.

## 2026-10-29 — Bind launcher diagnostics to the real compositor display

- Runtime 40738943260 reports a real Quickshell instance on wayland-1 but
  exit255 for a cleared diagnostic environment whose display is "unk". Add
  a high-level regression requiring WAYLAND_DISPLAY from a verified compositor
  socket, not from an IPC filename convention or hard-coded wayland-0/1.
- RED 40781383581 fails exactly because WAYLAND_DISPLAY=wayland-7 is absent
  from the launcher query. Revalidate the Niri IPC peer's UID/executable/root,
  then accept only a non-symlink Wayland socket with the same kernel PID/UID.
  Pass that verified basename to the cleared diagnostic environment; retain
  the optional timeout behavior and the final real panel/process check.
- Add selection tests rejecting another PID/UID, stale sockets, links, lock
  files and an unverified IPC endpoint. This does not claim launcher interaction.
- Source/profile GREEN 40781851858 at c193671; independent review has no
  P1/P2. Real payload GREEN 40782166125: verified wayland-1, 1280x800 with
  6743 colors after two attempts, query exit0. Exposes installs, volume,
  sidebar.toggle, brightness and media targets. This proves a real query,
  not launcher selection or app-start interaction. Preserve that distinction.

## 2026-10-29 — Observe the real-payload failure before changing behavior

- Probe `40729655376` completed with failure: installed Niri rejects the
  `validate` positional argument. Download, extraction, actual keyring commands
  and two hook applications reached this point; desktop execution did not.
- Add a GitHub-only existing-report inspection workflow and bounded automatic
  diagnostic tails. Inspect the previous report before adapting the command;
  do not download runtime artifacts to the user's desktop or rerun blindly.
- Upstream Niri v26.04 `src/cli.rs` declares global arguments conflicting with
  subcommands, while Validate owns its own config option. Add an initializer
  regression for `niri validate --config PATH` before correcting invocation.
- RED `40731682925` fails precisely at the rejected invocation in the new
  initializer regression (29 cases, one error, one expected toolkit skip).
  Move the config option into the validate subcommand; require source GREEN
  before dispatching the next real-payload probe.
- GREEN `40732235594` validates source and the actual locked Rust/profile.
  Independent readonly review reports no P1/P2. Address its two P3s: suppress
  workflow-command interpretation during diagnostic printing, and require a
  completed probe-workflow origin plus print its SHA before historical reads.
- Real run `40732626280` at `fa19516` proves actual initialization
  changed=true/false, UID1000 home and unchanged Niri configuration validity.
  Desktop then panics with XOpenDisplayFailed before shell startup. Xvfb only
  reports nonfatal xkb warnings. Add user-context socket/ancestor metadata and
  runner-only connect tracing to locate this fixture boundary before fixing it.
- Diagnostic RED `40734247676` fails before desktop launch with a direct
  UID1000 stat EACCES: /tmp is 1777 but /tmp/.X11-unix is root-owned 0700.
  Give only the disposable mount namespace a fresh 0755 tmpfs parent before
  binding the single Xvfb socket. Do not chmod the rootfs or expose all host
  X11 sockets. Add a source regression for mount order and user preflight;
  the actual namespace run remains the permission/desktop acceptance gate.
- `40735573507` at `d707843` passes the X11 boundary and starts actual
  Niri 26.04 plus `qs -c pond-shell`. Verified Niri IPC reports pond-wallpaper
  Background, pond-sidebar Top and pond-settings-winit Overlay. The probe's
  previous unverified exact `quickshell` namespace expectation rejects these.
  Admit only observed pond-sidebar/Top, not any pond/quickshell prefix or
  wallpaper/settings layer. Require the same panel again after screenshot.
- The same log warns that a 0755 X11 parent prevents xwayland-satellite from
  creating its own sockets. Use the standard 1777 mode on this private tmpfs
  only, retaining the single parent-socket bind and leaving host/rootfs modes
  unchanged. No screenshot, launcher, systemd or LightOS success yet claimed.
- Source/profile `40736809617` passes; independent review again finds no
  P1/P2. Runtime `40737041062` reaches the real panel and creates its PNG but
  rejects frame dimensions/colors. Keep the same threshold, expose actual
  metrics, and inspect that existing report's PNG only on GitHub before
  diagnosing rendering or startup timing. Do not claim first-frame acceptance.
- GitHub-only existing-report inspection `40737817253` verifies source SHA
  and measures the saved PNG: 1280x800, exactly one color. A mapped layer is
  not yet a rendered frame. Add a regression requiring bounded frame readiness
  (first blank, then nonuniform), without relaxing the dimensions/color gate.
- RED `40738136256` fails that exact new regression at 1280x800/one color.
  Separate frame readiness from layer mapping: retry newly requested safe PNGs
  with a 30-second retry budget, remove the previous fixture screenshot before each
  request, retain attempt metrics, and still reject permanently uniform frames.
  Keep process liveness and the final exact panel check; no threshold lowering.
- Source/profile GREEN `40738609224` at `1121af5`; 32 source cases include
  delayed-frame recovery and permanent-uniform rejection. Independent review
  finds no P1/P2. P3 clarification: the retry budget is soft because bounded
  in-flight IPC/PNG/identify operations can finish beyond it; it is not a
  strict 30-second wall-clock deadline. Real run `40738943260` dispatched once.
- Real GREEN `40738943260` at `1121af5`: actual hook changed=true/false,
  UID1000 home, original Niri config, exact native Pond sidebar and a
  1280x800/7999-color frame pass. Two frame requests demonstrate the initial
  mapping/render timing distinction. The final panel/process check also passes.
- Optional launcher diagnostic is still unaccepted: exit255 says the current
  display is "unk", while the real Quickshell instance is on wayland-1. Its
  separate cleared environment omitted WAYLAND_DISPLAY. Next bind that value
  to a verified socket owned by the same Niri peer; do not guess a socket name.
  This is real-payload fixture evidence, not actual LightOS systemd/proxy or
  persistent remoted-owner acceptance. Image build remains suspended.

## 2026-10-29 — Real payload initialization and native shell experiment

- Active goal remains a working LightOS image with normal initialization, not
  CLI-only completion. Previous turn is progress: source and exact-profile
  integration changed and passed real GitHub execution and independent review.
- Add a manual GitHub-only real-payload probe. Build the locked static Rust
  tools, verify/extract a fresh rootfs, apply real cleanup/profile installation,
  then isolate the runtime fixture from host PID, mount and network state.
- Model only observed platform prerequisites with synthetic identity/account;
  run the real Rust hook twice against Pond's actual GPG keyring. Preserve skel
  and run native Niri without --session on a private Xvfb display; require a
  Pond/Quickshell non-background layer and nonuniform screenshot, not empty Niri.
- Runtime fixture changes are never reused as an OCI build context. Upload
  bounded reports only, clear command environments, and terminate owned
  fixture processes on every exit. Remoted owner development stays deferred.
- This experiment is not actual LightOS systemd/proxy acceptance. The current
  instance lacks the external /lzcinit/lightosctl interface; do not bypass app
  authorization with sudo or private credentials. No image is declared complete.
- Source validation `40726881695` passes at `c584c63`. Fresh static review
  nevertheless finds two P2s before dispatch: a panel that disappears after
  the initial observation can pass with colorful wallpaper, and an optional
  launcher diagnostic timeout incorrectly discards desktop evidence. Add
  high-level mocked probe regressions and tighten the panel namespace admission
  to exact `quickshell`; observe their source RED before changing the probe.
- The namespace is an explicit strict probe expectation, not evidence that the
  locked payload has met it. The real run must demonstrate its actual layer;
  a mismatch fails rather than widening admission to arbitrary named panels.
- RED `40727974228` at `967b066` reproduces all intended assertions: a lost
  panel incorrectly returns success, diagnostic timeout escapes, and lookalike
  namespaces are admitted. Tighten exact matching, re-check process/layer
  after screenshot and diagnostics, and record an optional diagnostic timeout
  without discarding verified frame evidence. Require fresh source GREEN.
- Final: minor (deferred): cap all live log/capture buffers, not merely tails
  written to the command report. This trusted, timeout-bounded experiment is
  not a claim that every log file is byte-bounded.
- Final: minor (deferred): mocked TERM-to-KILL and rejected-peer identity cases.
  Real owned process cleanup and peer verification remain required in the run.
## 2026-10-28 — Explicit render-group recipe regression

- After accepting ordering, specify the next integration seam before changing
  the profile or toolkit pin: opt both canonical services into numeric mapped
  render-node groups and require the same Rust binary's generator symlink.
- The recipe still selects accepted toolkit `e682f78`, which has no generator;
  observe that meaningful source/real-CLI RED remotely. The toolkit's new
  capability must finish its independent CI/review before this recipe selects
  it. Do not generate device policy during offline install or restore the
  suspended image build; mapped devices belong to runtime, not an OCI layer.
- RED: source `86c1d1414759fef74a0a653dfd0690a59b8acdcd`, GitHub
  `40718944905`: source rejects the missing explicit policy and both existing/
  absent-settings CLI scenarios report `missing Rust render-group generator`.
- The mechanism gate is now GREEN: toolkit `30f7651`, full Actions
  `40718742320`, stable/MSRV/static-runtime all pass, including 49 Rust tests
  per required build and 20 chroot cases. Independent review finds no P1/P2;
  device-isolation wording is clarified because numeric groups are group-wide.
- Select exactly `30f76519e9d3c809c892fa1d71e1f8a23d87c577` and opt both
  canonical services into mapped render groups. Offline installation creates
  the same-binary generator link, never a runtime group policy. No Dockerfile
  change or image-build dispatch is part of this phase.
- GREEN: recipe `a86cbddf0f385a89585e3f410629f70ffb886824` passes source and
  real-toolkit/profile jobs in GitHub `40720297613`. Independent integration
  review finds no P1/P2; both existing/absent-settings scenarios install twice.
- Final: minor (deferred): compare the installed profile's parsed contents to
  the source profile, including render_node_services. Static review confirms
  the locked serializer preserves that field; this is not a current defect.
- Keep the group's actual permission scope explicit and leave actual service
  credentials/GPU, complete shell, persistent Niri owner and platform proxy
  acceptance open. No source/fixture result is a graphical release claim.

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
- Observed RED on GitHub run `40710876277`, exact regression revision
  `a26b46e4f9b9f9fc234b53d47786ab336ec6702e`: source job `122895484907`
  rejects the old profile and real-toolkit job `122895485516` reports
  `missing ordering for lightos-remote-desktop.service`. Toolkit compilation
  itself succeeded; the failure is the intended missing recipe wiring.
- Select already accepted toolkit `e682f7869062bdcc1024e5ef589a99143baaed59`
  and list exactly the two canonical services in the Pond profile. Add the
  absent-settings fixture alongside the opaque existing-settings fixture;
  both run installation twice with no usable external-command PATH.
- Reconcile desktop-gate documentation with completed offline AUR and isolated
  Niri capture/input/text-clipboard evidence. Persistent native owner and full
  Pond shell/platform/device acceptance remain open; no Dockerfile change or
  image-workflow dispatch is part of this phase.
- GREEN: revision `9b0d20ebc69c7451885bb12ec5f5d7b5d484c004` passed both
  `source` and `toolkit-profile` in GitHub run `40713790188`. The latter builds
  the locked Rust commands and executes both settings scenarios, twice each.
- Final review: a fresh read-only reviewer found no P1/P2 in the full wiring
  change. Deferred minors: syscall-level proof against auth reads and an
  existing `/dev/null` service-mask fixture; static review found no auth read.
  These are coverage improvements, not proven current leaks or mask changes.
- Next: specify and verify explicit numeric render-node group authorization
  in the Rust adapter. Do not change host nodes, guess usernames, or resume
  persistent-remoted-owner research to implement this independent prerequisite.

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
## 2026-10-29 — Native owner seam passes real transport reconnect

- Remoted `0fad9c9` / GitHub probe `40800711240` passes actual Niri ownership,
  relative includes, private launcher PATH and two authenticated transport
  generations. Red/blue application pixels are verified in decoded JPEGs;
  owner/Niri/foot PID-start identities remain unchanged across transport stop.
- The preceding run `40798343643` exposed unsupported automatic resize claims.
  Native owners now default to query-only output discovery; the original
  resize-denial assertion remains, rather than relaxing acceptance.
- Normal owner shutdown proves no live fixture descendants before fallback.
  Abrupt publisher cancellation and private-log alias boundaries have separate
  new regression gates; do not claim their success before actual CI evidence.
- Image construction stays paused until those necessary extension checks close.
  Next is the actual Pond shell via this owner/transport, then boot/settings
  ordering and amd64 dual-registry publication, not more codec/AUR research.

## 2026-10-29 — Close required remoted extension and resume real payload integration

- Accepted source `78acffa733bb3ffe7ef10d214ab525602f996454` passes actual
  native-owner probe `40801658254` and the full Linux job `123210926934` in
  `40801657709`: both features' tests/clippy, cancellation/log safety,
  FreeRDP/X11, packaging and installer contracts. Independent narrow review
  finds no new P1/P2. Do not describe unrelated codec/cursor/native-host jobs
  as green; they are outside this accepted Linux owner seam.
- Add a separate GitHub-only real-Pond-through-remoted probe using that exact
  source. Build and download only on GitHub; preserve original rootfs/config,
  require genuine Pond shell process identities and native sidebar, receive
  authenticated remote JPEGs in two transport generations, then inspect decoded
  colors and normal cleanup. This is a disposable fixture, not a packaged image.
- Add protocol boundary cases for complete, extended, oversized, truncated and
  unsupported WebSocket frames. First execution remains pending; missing Cage
  or other payload prerequisites must report their real failure before any
  package changes. Launcher app-start and actual platform boot/proxy remain
  explicit later acceptance rather than assumed results.

- First actual remote-payload run `40803934219` reaches the rootfs preflight,
  but rejects `qs` before executing the desktop. The outer `Path.is_file()`
  follows an absolute rootfs symlink in the runner's filesystem, unlike the
  previously accepted real-payload boundary. Check executability using `test -x`
  inside the disposable namespace and report all missing prerequisites together;
  do not install packages based on this misleading outer-path failure. HTTP
  fixture identity was separately corrected to explicit `lightos` at `60cb422`.

- Independent review finds one P2 in the new fixture: its stop helper accepts
  early process exit and ignores failure status after TERM. Real subprocess
  regressions at `81ab9a4` / source run `40805012141` observe three intended
  failures (early 0/17 and post-TERM 19). Require live-before-TERM and successful
  exit for acceptance; keep best-effort fallback cleanup separate in `finally`.
  The accepted remoted binary already returns zero on normal TERM, as required
  by its previously green actual-owner test. Do not accept a crashed transport
  as successful reconnect/shutdown merely because its desktop survived.

- Correct namespace preflight `40804832799` now confirms the actual missing
  dependency is Cage only; Niri, `qs`, Python and setpriv are present. Add the
  explicit recipe package-preparation stage before cleanup: native pacman with
  full Arch upgrade plus Cage, existing signature policy unchanged, network
  available only for that isolated GitHub package transaction, and full installed
  version manifest retained. Subsequent runtime remains network-isolated. This
  is a package-set change, not a claim that the pristine archive already works;
  rerun actual desktop acceptance and surface any keyring/repository failure.

- Preserve dependency caches on GitHub for both reviewed Rust workspaces,
  including failed runtime probes. Pin the cache action's exact revision and
  keep lockfile/toolchain/native-build environment hashing. Cargo still builds
  the selected source normally; this does not download artifacts locally or
  substitute a cache hit for runtime acceptance.

- Package-preparation RED `40805866335` stops before pacman: bubblewrap cannot
  create `/etc/resolv.conf` because its runtime symlink destination has no
  parent directory in the extracted rootfs. Create the private package
  namespace's `/run/systemd/resolve` parent before the single read-only resolver
  bind and print only the public rootfs link metadata. Do not replace the
  upstream link or bind the runner's complete `/etc` or `/run`. The package
  signature, repository and desktop gates have not executed yet.

- Order the disposable rootfs/package preparation before frontend/remoted
  compilation. Only the static kit is needed for that first boundary, so DNS,
  repository or package failures now surface before the expensive desktop build.
  Successful probes still compile the exact accepted remoted source and execute
  the unchanged actual-desktop gate afterward.

- `40806895348` ends at a transient upstream download-body TCP reset before
  package preparation; `40807483270` subsequently downloads the same verified
  payload and confirms its resolver link is exactly
  `/run/systemd/resolve/stub-resolv.conf`. Creating the parent alone still fails
  while mounting through `/etc/resolv.conf`. Remove that shared premise: the
  rootfs owns the absolute link, while bubblewrap owns mount setup. Bind directly
  at the observed runtime target instead of asking setup to follow the alias.
  The rootfs link remains unchanged; no extra host configuration is exposed.

- Cache only the public compressed rootfs archive on GitHub under its exact
  SHA-256 key, with no fallback keys. The normal Rust fetch step always runs
  after restore and revalidates the digest; save only follows that successful
  validation and precedes runtime mutations. This removes repeated large public
  downloads without caching account state, test reports or initialized rootfs.

- Resolver-target run `40808148330` passes mount/DNS and reaches native pacman,
  which rejects an absent public keyring and unknown Pond repository key. The
  accepted Rust tool gains explicit offline preparation instead of a shell
  initializer, signature bypass or forged platform marker: `eea666f`, full
  toolkit CI `40809926162`, all 26 CLI runtime cases and independent review.
  Pin that exact implementation and prepare local Arch/Pond public trust before
  the package transaction; runtime apply keeps its existing platform prerequisite.
- Actual cleaner regression `161a4ae` / `40810680011` fails because the previous
  recipe retains synthetic build-private GPG state. Add an explicit cleanup rule
  for `etc/pacman.d/gnupg`, retaining packaged public rings and leaving all
  platform/user initialization markers absent. Package signing remains enforced;
  the changed recipe still needs its new source/profile and real-payload gates.

- Source/profile `40811000397` passes, and actual `40811262690` now completes
  offline real GPG preparation, the signed native package transaction, Cage
  installation, cleanup and synthetic first-boot initialization twice. Its real
  native Niri peer is admitted before the probe aborts with an IPC timeout.
  Container-only module/GRUB hooks also warn; this is not a physical boot claim.
- The readiness helper aborts on the first socket timeout instead of consuming
  its bounded readiness budget. Controlled real process/socket RED at `da4127d`
  / `40812463749` observes both transient and persistent timeout failures, while
  protocol errors still propagate. Retry only TimeoutError while the owner stays
  alive; keep the same total deadline and all exact layer/frame assertions.
- Preserve bounded owned regular-file tails of the actual Cage/Niri/Quickshell
  and private-bus logs, plus the exact runtime phase. Earlier reports retained
  only the outer owner's diagnostics and lost the children needed to diagnose
  an unresolved startup failure. Do not infer Pond-shell or JPEG success yet.

- Readiness/phase source and real-toolkit profile gates pass at `4e5f977` /
  `40812967616`. Independent review finds diagnostic collection can still mask
  the primary failure and prevent evidence writing. Real symlink/FIFO source
  RED `8491b42` / `40813631836` reproduces both cases without reading rejected
  content. Keep the no-follow/type/owner/size checks; record per-log optional
  diagnostic failures, continue the other log, and attempt evidence writing in
  its own finally. This does not convert a failed native desktop gate to success.

- `fabbfff` source/profile gates pass in `40813835065`. Actual
  `40814131202` reaches the unchanged native-sidebar readiness deadline;
  diagnostics show Niri 26.04 admitted, `qs -c pond-shell` activating its private
  bus, and no log-collection errors. Thus a longer wait alone is not the fix.
  Retain the failed gate and record actual Layers replies vs timeout counts,
  plus verified Niri/Quickshell wait channels and Qt platform module basenames
  before cleanup. Read no process environments or auth files. This distinguishes
  changed native layer names, unavailable Qt platform and blocked rendering
  without rewriting Pond config or substituting an empty compositor.

- On native-owner failure only, compare the previously proven raw Niri/Xvfb
  startup against the same updated, initialized disposable root. Retain separate
  comparison logs and explicitly record that this is a post-failure diagnostic,
  not a cold-start control or a substitute desktop acceptance. Always rethrow
  the original native failure, even when this comparison renders successfully.
  This distinguishes a changed package/config baseline from parent/backend
  integration without repeating the rootfs download and package transaction.
