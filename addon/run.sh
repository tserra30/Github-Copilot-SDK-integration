#!/usr/bin/with-contenv bashio

# Read GitHub token from add-on options
GITHUB_TOKEN=$(bashio::config 'github_token')
MCP_CONFIG=$(bashio::config 'mcp_config')

if bashio::var.is_empty "${GITHUB_TOKEN}"; then
    bashio::log.fatal "No GitHub token configured. Please set 'github_token' in the add-on options."
    exit 1
fi

# Authenticate the Copilot CLI using the token via environment variable.
# GH_TOKEN is picked up automatically by the CLI without interactive prompts.
export GH_TOKEN="${GITHUB_TOKEN}"

bashio::log.info "GitHub token configured via GH_TOKEN; not validated during bridge startup."
bashio::log.info "SDK clients check authentication and model access when they connect and send a request."
bashio::log.info "Copilot CLI runtime:"
copilot --version

if [[ -n "${COPILOT_CONNECTION_TOKEN:-}" ]]; then
    bashio::log.info "Bridge connection-token authentication is configured; SDK clients must provide the matching secret."
else
    bashio::log.info "Bridge connection-token authentication is not configured. The CLI warning about COPILOT_CONNECTION_TOKEN is separate from GitHub authentication."
    bashio::log.info "Any client that can reach port 8000 may connect; keep this port on a trusted internal network."
fi
bashio::log.info "Integration connection/session messages appear in Home Assistant logs under custom_components.github_copilot, not in this bridge log."

# Feature-detect optional CLI flags so the script works across pinned CLI versions.
# --no-auto-update: suppresses self-update checks that can cause unexpected behaviour.
# --log-level     : controls server verbosity.
# Use an array for the full argument list to avoid word-splitting issues.
# `|| true` prevents the script from aborting if `copilot --help` exits non-zero.
COPILOT_HELP=$(copilot --help 2>&1 || true)
COPILOT_HEADLESS_HELP=$(copilot --headless --help 2>&1 || true)
# Returns 0 if the given long flag name appears at the start of a line in the
# provided help text (option-list lines begin with optional whitespace then the
# flag), preventing false positives from flag names in descriptive prose.
has_flag() {
    local help_text="${1}" flag="${2}"
    printf '%s\n' "${help_text}" | grep -qE "^[[:space:]]*--${flag}([[:space:]=]|$)"
}
validate_mcp_config_file() {
    local config_file="${1}"

    if [ ! -f "${config_file}" ]; then
        return 1
    fi

    if command -v jq >/dev/null 2>&1; then
        jq -e 'type == "object" and (.mcpServers | type == "object")' "${config_file}" >/dev/null 2>&1
        return $?
    fi

    grep -qE '^[[:space:]]*\{' "${config_file}" && grep -qE '"mcpServers"[[:space:]]*:' "${config_file}"
}
# CLI 1.0.83 defaults to loopback; its supported --host flag is hidden from help.
# Bind inside the add-on network namespace, without publishing a host port.
COPILOT_ARGS=(--headless --host 0.0.0.0 --port 8000)
if has_flag "${COPILOT_HELP}" no-auto-update; then
    COPILOT_ARGS+=(--no-auto-update)
fi
if has_flag "${COPILOT_HELP}" log-level; then
    COPILOT_ARGS+=(--log-level info)
fi

TRIMMED_MCP_CONFIG=$(printf '%s' "${MCP_CONFIG}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
if ! bashio::var.is_empty "${TRIMMED_MCP_CONFIG}"; then
    # Flag availability can vary by CLI version/help surface; check both outputs.
    if ! has_flag "${COPILOT_HELP}" additional-mcp-config && ! has_flag "${COPILOT_HEADLESS_HELP}" additional-mcp-config; then
        bashio::log.warning "Custom MCP config was provided, but this Copilot CLI does not support --additional-mcp-config. Continuing without MCP tools."
    else
        MCP_CONFIG_FILE=""
        MCP_CONFIG_PATH=""

        # Accept either "/path/to/file.json" or "@/path/to/file.json".
        if [[ "${TRIMMED_MCP_CONFIG}" == @* ]]; then
            MCP_CONFIG_PATH="${TRIMMED_MCP_CONFIG#@}"
        elif [[ "${TRIMMED_MCP_CONFIG}" != \{* ]]; then
            MCP_CONFIG_PATH="${TRIMMED_MCP_CONFIG}"
        fi

        if [ -n "${MCP_CONFIG_PATH}" ]; then
            if [ ! -f "${MCP_CONFIG_PATH}" ]; then
                bashio::log.fatal "Invalid MCP config path '${MCP_CONFIG_PATH}': file does not exist."
                exit 1
            fi
            if [ ! -r "${MCP_CONFIG_PATH}" ]; then
                bashio::log.fatal "Invalid MCP config path '${MCP_CONFIG_PATH}': file is not readable."
                exit 1
            fi
            MCP_CONFIG_FILE="${MCP_CONFIG_PATH}"
            bashio::log.info "Using custom MCP config file: ${MCP_CONFIG_PATH}"
        elif [[ "${TRIMMED_MCP_CONFIG}" == \{* ]]; then
            CUSTOM_MCP_CONFIG_FILE=/tmp/copilot-custom-mcp-config.json
            printf '%s\n' "${TRIMMED_MCP_CONFIG}" >"${CUSTOM_MCP_CONFIG_FILE}"
            MCP_CONFIG_FILE="${CUSTOM_MCP_CONFIG_FILE}"
            bashio::log.info "Using inline MCP config from add-on options."
        fi

        if ! validate_mcp_config_file "${MCP_CONFIG_FILE}"; then
            bashio::log.fatal "Invalid mcp_config. JSON must be valid and include an object-valued 'mcpServers' property."
            exit 1
        fi

        ADDITIONAL_MCP_CONFIG_VALUE="@${MCP_CONFIG_FILE}"
        COPILOT_ARGS+=(--additional-mcp-config "${ADDITIONAL_MCP_CONFIG_VALUE}")
    fi
fi

# Start the Copilot CLI in headless server mode with a retry loop.
MAX_RETRIES=5
RETRY_DELAY=5
ATTEMPT=1

while true; do
    bashio::log.info "Starting GitHub Copilot CLI server on 0.0.0.0:8000 (attempt ${ATTEMPT})..."
    # Bashio enables errexit, so capture failure explicitly to reach the retry loop.
    EXIT_CODE=0
    copilot "${COPILOT_ARGS[@]}" || EXIT_CODE=$?

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
