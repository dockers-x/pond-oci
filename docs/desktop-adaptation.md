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

## Remaining gates

1. Recipe wiring passed GitHub run `40713790188` at `9b0d20e` after the
   missing-ordering RED in `40710876277`: both settings scenarios install
   twice, preserving package units and leaving remote services unenabled.
   Independent review found no P1/P2. Existing masks and syscall-level
   no-auth-read coverage are deferred improvements; this is offline evidence,
   not a boot or late-settings runtime acceptance.
2. Verify Pond shell/launcher startup and useful failure diagnostics. No real
   seed or platform authentication is needed or permitted in those fixtures.
3. A persistent native Niri owner remains required: preserve per-user includes
   and the compositor's application environment, and prove reconnect/transport
   upgrade leaves the desktop and its applications alive. The user deferred
   further remoted-owner work; do not substitute its current Hyprland owner or
   treat an empty Niri instance as completion.
4. Finish explicit device policy without changing host device permissions.
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
