# Native Pond desktop: evidence and remaining gates

## Observed payload

GitHub-only audit `40683134808` at recipe `d8dc698` succeeded without executing
rootfs programs. The locked rootfs provides Niri 26.04-1 and its ordinary
`niri-session` -> user `niri.service` -> `niri --session` login path.

The desktop is more than the compositor. Its skel Niri config includes personal
cfg files and a shell directory linked to
`/usr/share/pond-interface/config/niri/shell`. The actual regular shell config
starts `qs -c pond-shell`; the personal autostart file contains only a commented
example. Keep the shell, launcher, skel links and all relative include paths.
Starting an empty Niri instance is not equivalent to preserving Pond.

Niri upstream tag v26.04 resolves to
`8ed0da44d974c32c6877d2f4630c314da0717ecb`. Its source has Winit and TTY
backends. Winit is selected by an existing display, while `--session` removes
parent display variables. Its internal headless backend is for tests and is not
a public CLI session mode. Its protocol implementation contains wlr screencopy
and a v2 virtual pointer; this source fact is not capture/input runtime evidence.

Primary source locations at that revision:

- `src/main.rs`: main-session environment handling.
- `src/niri.rs`: display-dependent backend selection.
- `src/backend/winit.rs` and `src/backend/headless.rs`: renderer boundaries.
- `src/protocols/screencopy.rs` and `src/protocols/virtual_pointer.rs`.

## Ownership boundaries

- LightOS owns instance materialization, seed/account setup and later remote
  environment updates. It proxies authenticated browser traffic to remoted.
- The Rust kit handles explicit offline cleanup and post-setup ordering. The
  accepted ordering extension does not enable/start platform or package units.
- The remote-desktop program owns service definitions and the graphical owner.
  Its current default owner is Cage/Hyprland, not Niri. Offline AUR staging is
  necessary but cannot substitute for a native Niri owner.
- The Pond recipe owns package choices, compositor selection and cleanup policy.
  It must not put Pond-specific behavior into generic rootfs tools.

Preserve the canonical two service names and environment paths. Do not source
credentials in a second initializer, invent admin APIs, or bake auth into the
image. `/var/lib/lightos/initialized` is only the first-boot boundary: later
remote settings may still be missing or disabled.

## Verified prerequisites

- Remoted v0.1.22 offline staging passed exact-tag CI `40685354147`, Arch
  codec publication `40687539494` and AUR publication `40687977677`. The
  subsequent main-package revision 0.1.22-2 adds the ABI-matched Hyprland
  cursor companion; AUR run `40708466590` and source CI `40708400112` passed.
  Its live-host repair did not restart the persistent session. This does not
  make that Hyprland-specific companion a Niri owner.
- Isolated Niri capture `40689971420`, actual pointer/keyboard delivery
  `40697001655` and bidirectional Unicode text clipboard `40699256007` passed
  on GitHub. These prove those individual seams, not the full Pond desktop.
- Toolkit revision `e682f7869062bdcc1024e5ef589a99143baaed59` passed source,
  minimum-Rust and static/runtime CI `40684692564`. Its ordering extension
  is now selected by this recipe and exercised against the actual Pond profile
  in the separate `toolkit-profile` validation job. That job does not build an
  image or start a service.
- Numeric render-group mechanism `30f7651` passed full toolkit Actions
  `40718742320` and independent review: 49 Rust tests per required build and
  20 isolated chroot cases. This recipe now selects that exact revision and
  explicitly opts both canonical services in. Its generator inspects mapped
  render character metadata and emits additive numeric group policy before
  systemd loads units; it never changes device permissions or account/auth
  state. Groups are group-wide rights, not single-device ACLs.
- The recipe's render policy passed `40720297613` at `a86cbdd`, after
  missing-generator RED `40718944905`. Source checks and the actual locked
  Rust CLI/profile installation both pass; fresh integration review found no
  P1/P2. Installed-profile readback is a deferred coverage improvement, not
  evidence of a current serialization defect.

## Remaining gates

The actual locked payload now passes init and native-frame fixtures:
40738943260 verifies keyring idempotence, the original Niri configuration,
pond-sidebar/Top and a 1280x800/7999-color image after two frame requests.
40782166125 additionally selects wayland-1 by the same authenticated Niri
PID/UID and obtains a real Quickshell IPC query with exit0 (6743-color image).
This is not a launcher click/app-start or real systemd/LightOS acceptance.

1. Recipe wiring passed GitHub run `40713790188` at `9b0d20e` after the
   missing-ordering RED in `40710876277`: both settings scenarios install
   twice, preserving package units and leaving remote services unenabled.
   Independent review found no P1/P2. Existing masks and syscall-level
   no-auth-read coverage are deferred improvements; this is offline evidence,
   not a boot or late-settings runtime acceptance.
2. Native shell startup, actual rendered frame and display-bound IPC query
   pass. Launcher/app-start interaction remains open. No real seed or platform
   authentication is needed or permitted in those fixtures.
   The audited Mod+Space binding calls vicinae toggle; sidebar.toggle only
   expands/collapses the sidebar. A future native-input fixture must observe
   the real launcher and a previously absent application window/process, not
   infer app-start from command exit0, an early launch log or screenshot hashes.
   Welcome-layer dismissal and accessibility labels must first be checked
   against the locked payload, not assumed from current upstream QML.
3. A persistent native Niri owner remains required: preserve per-user includes
   and the compositor's application environment, and prove reconnect/transport
   upgrade leaves the desktop and its applications alive. The native-owner
   seam is now resumed narrowly as a direct image dependency; unrelated
   codec/cursor/AUR research stays out of scope. Do not substitute the current
   Hyprland owner or treat an empty Niri instance as completion.
   Remoted `0fad9c98650a9a0729dcc0bc3053869b805eed01` / GitHub probe
   `40800711240` now passes that generic owner seam: actual Niri and an
   included foot application survive two authenticated transport generations,
   each delivering newly requested red/blue JPEG application pixels. Native
   includes and PID-start identities remain unchanged; ordinary owner stop
   leaves no live fixture children. Actual Niri/private-bus PATH is checked.
   Unsupported automatic resize remains disabled. This is not yet the locked
   Pond shell through the transport or a platform proxy/boot acceptance; remoted
   cancellation and log-alias hardening regressions initially failed in
   `40800945917`, then pass at `78acffa733bb3ffe7ef10d214ab525602f996454`:
   Linux job `123210926934` in `40801657709` passes both regressions, complete
   default and RDP/portal suites, fmt/clippy, FreeRDP/X11 and package/installer
   guards. Actual native-owner probe `40801658254` also passes again; independent
   narrow review reports no new P1/P2. This closes the required generic native
   owner extension gate, not the separate full cross-platform repository CI.
   The new GitHub-only `probe-remote-desktop.yml` pins that accepted source and
   exercises it against the locked Pond payload. It must observe real
   `qs -c pond-shell` process identities, the native sidebar and decoded remote
   JPEGs over two transport generations before normal cleanup. It intentionally
   first reports missing rootfs dependencies instead of silently adding them.
   Actual run `40804832799` now verifies `niri`, `qs`, Python and `setpriv`
   inside the rootfs namespace and rejects only missing `cage`. The recipe's
   next explicit preparation step installs Cage with a supported Arch full
   package transaction before cleanup, preserving signature checks and recording
   `pacman -Q` provenance. This changes the base package set and requires a fresh
   native desktop acceptance; it is not evidence about the untouched archive.
4. Verify the explicit device policy on actual service processes without
   changing host device permissions. Numeric-policy generation is accepted,
   but real process credentials/GPU rendering have not been exercised here.
   Bind-mounted GPU groups are numeric identities, not necessarily the named
   video/render groups in the rootfs. Apply authorization to the actual owner
   and transport separately. Software rendering must not require a physical VT.
5. Verify boot-time platform ordering and late runtime settings, including a
   disabled remote service. Physical VT handoff remains a separate optional
   target; do not guess the VT-manager socket protocol.
6. Close the CLI extension gate with remote evidence and independent review.
   Only then resume amd64 OCI construction and dual-registry publication.

No desktop OCI image or real LightOS proxy/VT acceptance is claimed by this
document. All builds, rootfs/package downloads and executable checks stay in
GitHub Actions; the running host is never a test fixture.
