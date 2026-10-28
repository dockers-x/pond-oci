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

## Remaining gates, in order

1. Finish the remoted offline-staging release through exact-tag CI, Arch codec
   publication and both real AUR packages. Keep normal live installation intact.
2. Exercise an isolated Niri candidate in GitHub before choosing an owner
   adapter: native first frame, pointer/keyboard and clipboard, correct output,
   Pond shell/launcher startup and useful failure diagnostics. No real seed or
   platform authentication is needed or permitted in those fixtures.
3. Extend the Rust session owner without guessing Hyprland signatures or
   capturing Cage instead of Niri. Preserve per-user Niri includes and the
   compositor's application environment. Prove reconnect/transport upgrade
   does not kill the persistent desktop or its applications.
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
