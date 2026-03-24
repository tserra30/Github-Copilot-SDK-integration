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

# Verify that the CLI can read auth state before attempting to start the server.
# Newer Copilot CLI versions use prompt mode for this check, while older
# versions support the dedicated 'auth status' command. Both checks are wrapped
# in a timeout so a CLI that waits for user input cannot block add-on startup.
# These checks are best-effort only: a GH_TOKEN-only setup can still work even
# if this probe fails.
bashio::log.info "Verifying GitHub Copilot CLI authentication..."
if timeout 10 copilot -p "auth status" --silent >/dev/null 2>&1 || timeout 10 copilot auth status >/dev/null 2>&1; then
    bashio::log.info "Authentication probe completed."
else
    bashio::log.warning "Copilot CLI auth probe failed. This can be expected with token-only setups. Proceeding to start the server; check server logs if authentication fails at runtime."
fi

# Feature-detect optional CLI flags so the script works across pinned CLI versions.
# --bind 0.0.0.0  : ensures the server is reachable from other Supervisor-network containers.
# --no-auto-update: suppresses self-update checks that can cause unexpected behaviour.
# --log-level     : controls server verbosity.
COPILOT_HELP=$(copilot --help 2>&1 || true)
BIND_FLAGS=""
EXTRA_FLAGS=""
if echo "${COPILOT_HELP}" | grep -q -- "--bind"; then
    BIND_FLAGS="--bind 0.0.0.0"
fi
if echo "${COPILOT_HELP}" | grep -q -- "--no-auto-update"; then
    EXTRA_FLAGS="${EXTRA_FLAGS} --no-auto-update"
fi
if echo "${COPILOT_HELP}" | grep -q -- "--log-level"; then
    EXTRA_FLAGS="${EXTRA_FLAGS} --log-level info"
fi

# Start the Copilot CLI in headless server mode with a retry loop.
MAX_RETRIES=5
RETRY_DELAY=5
ATTEMPT=1

while true; do
    bashio::log.info "Starting GitHub Copilot CLI server on port 8000 (attempt ${ATTEMPT})..."
    # shellcheck disable=SC2086
    copilot --headless ${BIND_FLAGS} ${EXTRA_FLAGS} --port 8000
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
