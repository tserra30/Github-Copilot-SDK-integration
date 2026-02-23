ARG BUILD_FROM
FROM $BUILD_FROM

# Install Node.js and npm
RUN apk add --no-cache nodejs npm bash

# Install the GitHub Copilot CLI
RUN npm install -g @github/copilot-cli

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
