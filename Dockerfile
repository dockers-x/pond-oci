# syntax=docker/dockerfile:1.7
ARG RUST_IMAGE=rust:1-alpine
ARG STAGING_IMAGE=archlinux:base

FROM ${RUST_IMAGE} AS kit
RUN apk add --no-cache build-base
WORKDIR /work/oci-kit
COPY --from=oci-kit /Cargo.toml /Cargo.lock /work/oci-kit/
COPY --from=oci-kit /crates/ /work/oci-kit/crates/
RUN cargo build --locked --release --workspace --bins

FROM ${STAGING_IMAGE} AS staging
RUN pacman -Syu --noconfirm --needed libarchive zstd
COPY --from=kit /work/oci-kit/target/release/rootfs-cleaner /usr/local/bin/rootfs-cleaner
COPY --from=kit /work/oci-kit/target/release/lighos-init /usr/local/bin/lighos-init
COPY profiles/ /work/profiles/
RUN --mount=type=bind,from=rootfs,source=/pond-rootfs.tar.zst,target=/input/rootfs.tar.zst,readonly \
    mkdir -p /rootfs && \
    bsdtar --numeric-owner --acls --xattrs -xpf /input/rootfs.tar.zst -C /rootfs && \
    rootfs-cleaner mark --root /rootfs && \
    rootfs-cleaner clean --root /rootfs --policy /work/profiles/cleanup.toml --apply && \
    lighos-init install --root /rootfs --config /work/profiles/lightos.toml && \
    while IFS= read -r unit; do \
      case "$unit" in ''|*[!A-Za-z0-9@_.-]*|..*) exit 2 ;; esac; \
      ln -sfnT /dev/null "/rootfs/etc/systemd/system/$unit"; \
    done < /work/profiles/masked-units.txt && \
    ln -sfnT /usr/lib/systemd/system/multi-user.target /rootfs/etc/systemd/system/default.target && \
    rm /rootfs/.oci-kit-staging && \
    test -x /rootfs/usr/lib/systemd/systemd

FROM scratch
ARG ROOTFS_SHA256
ARG OCI_KIT_REVISION=development
LABEL org.opencontainers.image.title="Pond for LightOS (experimental)" \
      org.opencontainers.image.source="https://github.com/dockers-x/pond-oci" \
      so.butterfly.rootfs.sha256="${ROOTFS_SHA256}" \
      eu.ca-x.oci-kit.revision="${OCI_KIT_REVISION}"
COPY --from=staging /rootfs/ /
ENV LANG=C.UTF-8
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
