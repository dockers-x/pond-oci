# One-click upstream desktop release

**Goal:** One manual `Release Pond image` workflow on main resolves upstream,
automatically allocates an immutable downstream SemVer tag, builds/verifies and
publishes the same amd64 desktop artifact to Docker Hub/GHCR and GitHub Release.

**Evidence:** 41398217407 fails because the old policy only accepts rc.1;
main dispatch silently skips actual publication. Old candidates expire after
three days. Upstream currently declares only a new SHA, not a SemVer.

**Policy:** Continue experimental `MAJOR.MINOR.PATCH-rc.1`, automatically advance
PATCH above existing tags (including user-created v0.1.4), never move tags or
claim real LightOS proxy acceptance. Same upstream + recipe + tool pins skips
completed releases after remote verification; a matching pending draft resumes
the same immutable artifact instead of rebuilding a conflicting image.

1. Add source/identity/version planning and tests; keep latest resolution static.
2. Convert proven desktop build into an internal callable workflow, preserving
   final-layer fidelity and native gates; feed the resolved lock/version once.
3. Add single dispatch orchestrator, actual systemd boot, draft release receipt
   before registry mutation, digest-preserving dual publication/readback and
   completion. Retry an existing tag only if exact source/digests match.
4. Remove superseded manual diagnostic/headless/publication workflows and stale
   candidate locks; keep automatic source/profile validation and internal build.
5. Independently review, run source tests and actual release on GitHub only;
   update README/WORK_LOG and SSH commit/push main at each stage.

Downloads/build/tests remain GitHub-only. No host credentials, services or
devices are used. Old published tags/releases remain untouched.
