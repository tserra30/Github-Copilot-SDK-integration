ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
FROM $BUILD_FROM

# Install curl, ca-certificates, and tar.
# Debian natively supports glibc, so the Copilot CLI binary runs without
# compatibility shims.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates tar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install the GitHub Copilot CLI from a pinned release, verifying the SHA-256 checksum.
# Only linux/amd64 and linux/arm64 binaries are published; other architectures are unsupported.
ARG COPILOT_VERSION=v0.0.418
RUN case "$(uname -m)" in \
      x86_64)  ARCH="x64"   ;; \
      aarch64) ARCH="arm64" ;; \
      *) echo "Unsupported architecture: $(uname -m)" && exit 1 ;; \
    esac && \
    ASSET="copilot-linux-${ARCH}.tar.gz" && \
    BASE_URL="https://github.com/github/copilot-cli/releases/download/${COPILOT_VERSION}" && \
    curl -fsSL "${BASE_URL}/SHA256SUMS.txt" -o /tmp/SHA256SUMS.txt && \
    curl -fsSL "${BASE_URL}/${ASSET}" -o "/tmp/${ASSET}" && \
    cd /tmp && grep " ${ASSET}$" /tmp/SHA256SUMS.txt | sha256sum -c - && \
    mkdir -p /tmp/copilot_extract && \
    tar -xzf "/tmp/${ASSET}" -C /tmp/copilot_extract/ && \
    find /tmp/copilot_extract -name "copilot" -type f | head -1 | xargs -I{} mv {} /usr/local/bin/copilot && \
    chmod +x /usr/local/bin/copilot && \
    rm -rf "/tmp/${ASSET}" /tmp/SHA256SUMS.txt /tmp/copilot_extract

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
