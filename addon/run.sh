#!/usr/bin/with-contenv bashio

# Read GitHub token from add-on options
GITHUB_TOKEN=$(bashio::config 'github_token')

if bashio::var.is_empty "${GITHUB_TOKEN}"; then
    bashio::log.fatal "No GitHub token configured. Please set 'github_token' in the add-on options."
    exit 1
fi

# Authenticate the Copilot CLI using the token via environment variable
bashio::log.info "Authenticating GitHub Copilot CLI..."
export GH_TOKEN="${GITHUB_TOKEN}"
copilot auth login

# Start the Copilot CLI in headless server mode, binding to all interfaces
bashio::log.info "Starting GitHub Copilot CLI server on port 8000..."
exec copilot --headless --port 8000 --bind 0.0.0.0
