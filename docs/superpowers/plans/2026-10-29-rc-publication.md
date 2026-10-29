# Publish the verified desktop candidate as an RC

- User authorized 0.1.0-rc.1, not stable 0.1.0 or latest.
- Systemd boot 40836935044 is GREEN for candidate 40835359201, including
  seeded UID/home setup, idempotence, healthy units and missing-seed rejection.
- First observe GitHub source-test RED for RC policy/config preservation, then
  implement strict RC-only promotion. Change only the OCI version label, never
  the filesystem, history, architecture, command or other provenance labels.
- Bind the source archive SHA and successful boot run to the same candidate lock.
- Re-run the actual systemd probe against the promoted artifact on GitHub.
- Review independently; publish that one artifact to GHCR and Docker Hub,
  verify identical remote digests/config and create a GitHub prerelease receipt.
- Real LightOS proxy/auth and launcher interaction remain explicit limitations.
