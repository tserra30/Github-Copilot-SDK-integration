ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

# Install curl and ca-certificates for downloading the Copilot CLI binary.
RUN apk add --no-cache curl ca-certificates

# Install the GitHub Copilot CLI by downloading the binary from GitHub releases.
# The binary name is determined by the host architecture.
RUN case "$(uname -m)" in \
      x86_64)  ARCH="amd64" ;; \
      aarch64) ARCH="arm64" ;; \
      armv7l)  ARCH="arm"   ;; \
      armv6l)  ARCH="arm"   ;; \
      *) echo "Unsupported architecture: $(uname -m)" && exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/github/copilot-cli/releases/latest/download/copilot-linux-${ARCH}" \
      -o /usr/local/bin/copilot && \
    chmod +x /usr/local/bin/copilot

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
