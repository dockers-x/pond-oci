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
