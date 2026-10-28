# Real Pond payload initialization and graphical acceptance

## Objective

Advance the active goal: build an image that runs on LightOS and initializes
normally. Passing source tests or generating unit files is insufficient.

The previous phase made concrete progress: the Rust mechanisms and actual Pond
profile passed GitHub execution and independent reviews. The next critical seam
is the locked distribution payload, not more mock coverage or remoted research.

## First executable experiment

1. On GitHub only, build the locked Rust tools, verify/download the locked
   rootfs and extract it into a separately marked disposable staging directory.
   Apply the real cleanup policy and install the actual Rust profile.
2. Exercise the observed platform prerequisite in an isolated mount/PID/network
   fixture: machine identity, base Arch keyring and one synthetic account with
   the real skel. Only then create the platform completion marker. This models
   materialization; it is not a claim to execute the external LightOS control
   plane or consume a real seed.
3. Run the installed Rust initializer twice against the actual Pond keyring;
   require changed=true then false, preserved home ownership and no invented
   remote credentials. Exercise the installed generator without hardware.
4. Start the payload's native Niri with its unchanged per-user config on an
   isolated Xvfb parent display. Do not pass --session, replace the compositor
   or run an empty hand-written desktop config. Require the real Pond shell's
   non-background layer, an actual Niri socket/executable and a nonuniform
   screenshot; report launcher IPC diagnostics for the next acceptance step.
5. Upload only synthetic-fixture reports/screenshots, not runtime roots. Screenshot
   and command-report tails are bounded; live process logs still need byte caps.
   Never upload or
   package the mutated runtime root, and never download it to the user's host.
   Dispose of every fixture process even on failure.

## Limits and follow-through

- All processes, dependencies and rootfs artifacts remain on GitHub; no host
  service, device permission, identity or authentication is changed.
- Use cleared environments and private process/network/mount namespaces. This
  is a trusted distribution-payload test, not a sandbox for malicious root.
- Persistent native owner work in remoted stays deferred. First obtain useful
  evidence about the real Pond shell before deciding the minimum mainline
  adapter needed to connect it to the existing canonical remote services.
- A successful fixture does not prove actual systemd boot, GPU credentials,
  external platform initialization/proxy or transport persistence. Keep those
  gates open and continue toward real image and LightOS-instance evidence.
- The suspended headless Dockerfile/workflow is not restored by this probe.

## Evidence ledger

- Initial state: oci-kit 5d36b78 / Actions 40720370623 and pond-oci ce59b67 /
  Actions 40721271853 pass. No completed desktop OCI or real instance is claimed.
- The current instance has no /lzcinit/lightosctl mount. Sudo is not external
  app authorization; do not invent a control API or inspect credentials to
  bypass this. Continue runner-side construction and acceptance meanwhile.
- `40729655376` at `9a29245`: initial real probe reached Niri validation but
  used the wrong CLI argument order. Regression RED `40731682925` then
  source/profile GREEN `40732235594` establish the fix at `fa19516`.
- `40732626280` at `fa19516`: actual keyring hook changed=true then false,
  UID1000 home and the unchanged Niri configuration pass. Desktop startup
  instead fails at XOpenDisplayFailed; no shell or graphical success claimed.
- `40733935870` at `ba8bc68`: source/profile validation passes with added
  socket metadata and runner-only connect tracing. Real diagnostic run
  `40734247676` is dispatched once; observe it before changing fixture policy.
- `40734247676`: UID1000 cannot stat the socket because its root-owned parent
  is mode 0700. Mask only that parent with a private 0755 tmpfs before binding
  the one runner Xvfb socket; leave rootfs and host directory modes untouched.
- `40735573507`: Niri and Pond Quickshell start and publish the actual
  `pond-sidebar` Top layer, wallpaper and first-run settings overlay. Replace
  the previously unverified `quickshell` namespace expectation with this exact
  panel/layer pair, not a name prefix. Give the private X11 tmpfs standard 1777
  permissions so xwayland-satellite can create its own sockets as UID1000.
