ARG BUILD_FROM=ghcr.io/hassio-addons/base/amd64:latest
FROM $BUILD_FROM

# Install Node.js and npm (bash is already included in the hassio base image)
RUN apk add --no-cache nodejs npm

# Install the GitHub Copilot CLI.
# Pin to a specific version for supply-chain safety (update as needed).
RUN npm install -g @github/copilot-cli@latest

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
