#!/usr/bin/with-contenv bashio

# Read GitHub token from add-on options
GITHUB_TOKEN=$(bashio::config 'github_token')

if bashio::var.is_empty "${GITHUB_TOKEN}"; then
    bashio::log.fatal "No GitHub token configured. Please set 'github_token' in the add-on options."
    exit 1
fi

# Authenticate the Copilot CLI using the token via environment variable.
# GH_TOKEN is picked up automatically by the CLI without interactive prompts.
export GH_TOKEN="${GITHUB_TOKEN}"

# Verify that the CLI is authenticated before attempting to start the server.
# NOTE: 'copilot auth status' checks for a persisted login session.  When only
# GH_TOKEN is set (no interactive login has been performed), the check may
# return non-zero even though the server will authenticate fine via the token.
# We therefore treat a failing status as a warning rather than a fatal error so
# that the add-on can still start; the server log will surface any real auth
# problems.
bashio::log.info "Verifying GitHub Copilot CLI authentication..."
if copilot auth status; then
    bashio::log.info "Authentication verified."
else
    bashio::log.warning "Copilot CLI auth status check failed. This is expected when using a raw GH_TOKEN without a persisted session. Proceeding to start the server -- check the server logs if authentication fails at runtime."
fi

# Start the Copilot CLI in headless server mode with a retry loop.
MAX_RETRIES=5
RETRY_DELAY=5
ATTEMPT=1

while true; do
    bashio::log.info "Starting GitHub Copilot CLI server on port 8000 (attempt ${ATTEMPT})..."
    copilot --headless --port 8000 --bind 0.0.0.0
    EXIT_CODE=$?

    if [ "${EXIT_CODE}" -eq 0 ]; then
        bashio::log.info "GitHub Copilot CLI server exited normally. Stopping add-on."
        exit 0
    fi

    if [ "${ATTEMPT}" -ge "${MAX_RETRIES}" ]; then
        bashio::log.fatal "GitHub Copilot CLI server failed after ${MAX_RETRIES} attempts (last exit code: ${EXIT_CODE}). Check the logs above for details."
        exit "${EXIT_CODE}"
    fi

    bashio::log.warning "GitHub Copilot CLI server exited with code ${EXIT_CODE}. Retrying in ${RETRY_DELAY} seconds..."
    sleep "${RETRY_DELAY}"
    ATTEMPT=$((ATTEMPT + 1))
done
