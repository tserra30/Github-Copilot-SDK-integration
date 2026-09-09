# GitHub Copilot Instructions for GitHub Copilot Home Assistant Integration

## Project Overview

This repository contains a Home Assistant custom integration that implements a conversation agent using the GitHub Copilot SDK and CLI. Read `README.md` for setup and `CONTRIBUTING.md` for development and manual MCP validation.

## Technology Stack

- Python, using the version supported by the Home Assistant dependency
- Home Assistant's config flow and conversation entity APIs
- Upstream `github-copilot-sdk` from PyPI
- Ruff, configured in `.ruff.toml`
- Dev container configuration in `.devcontainer.json`

## Code Style and Standards

- Use type hints with `from __future__ import annotations`
- Use async/await for I/O; offload blocking filesystem operations from Home Assistant's event loop
- Follow Home Assistant conventions and existing code patterns
- Use PascalCase for classes, snake_case for functions and variables, and UPPER_SNAKE_CASE for constants
- Add docstrings to public functions and classes
- Keep comments minimal and meaningful
- Preserve backward compatibility for existing integration configuration
- Use custom API exceptions and user-friendly errors without revealing secrets

## Project Structure

```text
custom_components/github_copilot/
├── __init__.py           # Integration entry point
├── api.py                # GitHub Copilot SDK client
├── config_flow.py        # Configuration UI flow
├── conversation.py       # Conversation agent implementation
├── coordinator.py       # Data update coordinator
├── const.py              # Constants and configuration
└── data.py               # Data models

addon/
├── Dockerfile           # Container image with pinned Copilot CLI
├── config.yaml          # Add-on metadata and configuration schema
├── run.sh               # Server startup, auth, and retry logic
├── build.yaml           # Multi-architecture build configuration
└── CHANGELOG.md         # Add-on version history
```

## SDK and Runtime Conventions

- Keep `custom_components/github_copilot/manifest.json` and `requirements.txt` SDK pins aligned
- The current upstream SDK is `github-copilot-sdk==1.0.13`, with a universal `py3-none-any` wheel; do not restore patched wheels or the obsolete custom wheel-build workflow
- Home Assistant Core's container is Alpine/musl, not an old-glibc environment
- SDK 1.0.13 pins CLI 1.0.83; compatible upstream runtimes include musl and glibc amd64/arm64 builds
- In local mode, let the SDK download and checksum its matching runtime when no installed or explicit executable is available; do not require manual binary installation or boot-time download hacks
- In remote mode, use the keyword-argument SDK API and `RuntimeConnection.for_uri`; do not download or require a local CLI binary
- A configured CLI URL and a local GitHub token are mutually exclusive SDK inputs: the bridge handles its own GitHub authentication
- Use a GitHub fine-grained PAT with **Account permissions → Copilot Requests → Read and write**; do not recommend classic PATs or a nonexistent classic `copilot` scope
- Keep connection validation in `async_test_connection()` and use the SDK rather than mimicking a raw Copilot API

## MCP Configuration and Authorization

- The integration's MCP field accepts inline JSON containing `mcpServers` or a Home Assistant-readable JSON file path, optionally prefixed with `@`
- Validate MCP configuration in both setup and options flows; load files off the event loop and report invalid JSON, unreadable files, and invalid server definitions instead of silently accepting or ignoring them
- Normalize legacy transport and working-directory aliases; canonical remote definitions use `type: "http"` or `"sse"`, `url`, `tools`, and optional `headers`
- Pass validated definitions through the SDK session's `mcp_servers` keyword argument
- Register a permission callback that approves only configured MCP servers and their allowed tools
- Preserve `tools: ["*"]` or explicit tool-name allowlists; deny unknown or unconfigured servers/tools
- Disable built-in CLI tools; never replace the permission policy with blanket approval
- Require MCP configuration in the **integration field even in bridge mode**; add-on `mcp_config` alone does not authorize tools for this integration
- Treat MCP headers and configuration files as credentials; never log or commit tokens

### Home Assistant MCP Validation

Use a current official Home Assistant Container or Home Assistant OS release. Integration metadata requires Home Assistant 2025.2.4 or later; an older 2024 development baseline does not contain the built-in MCP server.

The upgrade validation environment is official Home Assistant Container **2026.9.1** on Docker Engine in Ubuntu WSL2, with the built add-on image running as an external CLI server. There is no Supervisor in Home Assistant Container: do not present this as Home Assistant OS or full Supervisor add-on lifecycle validation. Record actual outcomes separately from the environment description.

Follow the checklist in `CONTRIBUTING.md`: add **Model Context Protocol Server**, enable the **Assist API**, expose a safe test helper, and configure `http://homeassistant:8123/api/mcp` from the bridge. Other deployments need an address reachable from the CLI runtime. Use a **Home Assistant long-lived token**, separate from the GitHub PAT, in its Bearer header. No external MCP server or proxy is needed.

Verify actual entity state changes, not just model text claiming success. Check invalid configuration and permission-denial paths as well as normal tool calls. Record what was actually tested without exposing credentials.

## Key Components

### Conversation Agent (`conversation.py`)

- Extend Home Assistant's `ConversationEntity` and implement `async_process()`
- Maintain session conversation history appropriately
- Respect response timeouts and API rate limits
- Return user-friendly errors

### Configuration Flow (`config_flow.py`)

- Validate credentials and configuration during setup
- Preserve Home Assistant's config flow patterns
- Support model, CLI URL, and MCP configuration options
- Keep the GitHub token optional for remote bridge connections
- Default new model selections to `auto`; preserve existing saved selections without silent migration
- Allow custom model IDs during setup and fetch live available model IDs for the options selector
- For an obsolete ID rejected with `Model not available` (for example `gpt-4.1`), direct users to choose a supported model through **Configure** instead of silently changing their choice

### Bridge Add-on (`addon/`)

- Run the CLI as a headless server on port 8000 on the internal Supervisor network
- Keep the CLI version and architecture-specific SHA256 checksums compatible with the SDK
- Preserve amd64/aarch64 support, token-based auth, feature detection, and bounded startup retries
- Bump `addon/config.yaml` for significant runtime changes and maintain `addon/CHANGELOG.md` using Keep a Changelog format
- Add-on `mcp_config` remains available to other bridge clients; do not confuse it with integration-level tool authorization

## Development and Validation

For a new development environment, install dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

Run the standard-library regression tests before lint and format checks for code changes. The tests use `unittest`, not an external runner:

```bash
python3 -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format . --check
```

Use `python -m ruff` rather than relying on a global `ruff` executable. `scripts/setup` installs dependencies; `scripts/lint` formats and auto-fixes in the dev environment. The development Home Assistant configuration is `config/configuration.yaml`.

The workflows in `.github/workflows/` are authoritative for CI: `lint.yml` checks Ruff, `validate.yml` runs hassfest and HACS validation, and `codeql.yml` runs CodeQL. Follow `CONTRIBUTING.md` for manual configuration, conversation, and MCP checks. Do not claim runtime testing passed based on lint alone.

## Documentation and Security

- Keep `README.md` and `CONTRIBUTING.md` aligned with user-facing and development changes
- Update translations when changing UI strings
- Maintain the add-on changelog for bridge changes
- Never commit API tokens, authorization headers, or other credentials
- Validate user input and avoid exposing sensitive data in error messages
- See `SECURITY.md` for security reporting and [Home Assistant developer documentation](https://developers.home-assistant.io/) for framework conventions
