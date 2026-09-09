# Contribution Guidelines

Contributing to the GitHub Copilot Home Assistant Integration should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Improving documentation

## GitHub is Used for Everything

GitHub is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Run the automated checks and test your contribution in Home Assistant.
4. Check linting and formatting with Ruff.
5. Issue that pull request!

## Development Environment

This integration is based on the [integration_blueprint template](https://github.com/ludeeus/integration_blueprint).

### Setup

1. Use the provided `.devcontainer.json` for Visual Studio Code development
2. The container includes a standalone Home Assistant instance
3. Configuration is in [`config/configuration.yaml`](./config/configuration.yaml)

For manual setup, install the development dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

Use a Python version supported by the Home Assistant dependency. For end-to-end MCP testing, use a current official Home Assistant Container or Home Assistant OS installation; an older development dependency baseline is not a substitute for testing the built-in MCP server.

### SDK Dependency

This integration uses upstream **`github-copilot-sdk==1.0.13`** from PyPI. Its universal `py3-none-any` wheel installs in Home Assistant Core's Alpine/musl container; no patched wheel or custom wheel-build workflow is needed. Keep the SDK pins in `custom_components/github_copilot/manifest.json` and `requirements.txt` aligned.

SDK 1.0.13 pins CLI **1.0.83**. In local mode, the SDK downloads and checksums a matching platform runtime when no installed or explicit executable is available, including musl builds. Remote bridge mode must not require or download a local CLI binary. Keep the bridge's CLI pin and architecture checksums compatible with the SDK, and update `addon/config.yaml` and `addon/CHANGELOG.md` for add-on changes.

### Automated Checks, Linting, and Formatting

Run the standard-library regression tests before linting. They use `unittest`, with no additional test-runner dependency:

```bash
python3 -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format . --check
```

### Auto-fixing Issues

```bash
python -m ruff check --fix .
python -m ruff format .
```

## Code Style

- Use **Ruff** for linting (configuration in `.ruff.toml`)
- Follow Home Assistant's coding standards
- Use type hints (`from __future__ import annotations`)
- Use async/await for I/O operations
- Document functions and classes with docstrings

## GitHub Copilot Integration Specific Guidelines

### API Client (`api.py`)

- All API methods should be async
- Include proper error handling with custom exceptions
- Use the SDK's keyword-argument API and `RuntimeConnection.for_uri` for remote connections
- Keep remote connection and local token authentication mutually exclusive
- Pass normalized MCP definitions through the session's `mcp_servers` argument
- Implement connection testing in `async_test_connection()`

### MCP Configuration and Permissions

- Accept inline JSON containing `mcpServers`, or an optional `@`-prefixed JSON file path readable by Home Assistant Core
- Validate MCP configuration in both setup and options flows; load files off the event loop and surface malformed or unreadable configuration rather than silently accepting or discarding it
- Use canonical remote `type: "http"` or `"sse"`, `url`, `tools`, and optional `headers`; normalize supported legacy transport and working-directory aliases
- Authorize only configured MCP servers and tools through the SDK permission callback; preserve explicit tool allowlists
- Disable built-in CLI tools and deny unknown or unconfigured MCP requests
- Require integration-level MCP configuration in bridge mode too; add-on `mcp_config` alone must not grant authorization
- Treat tokens and MCP authorization headers as secrets; do not expose them in logs or errors

### Conversation Agent (`conversation.py`)

- Extend `ConversationEntity` from Home Assistant
- Implement `async_process()` for message handling
- Maintain conversation history appropriately
- Handle errors gracefully with user-friendly messages

### Configuration Flow (`config_flow.py`)

- Validate credentials during setup
- Provide clear error messages
- Support optional configuration parameters
- Follow Home Assistant's config flow patterns
- Default new configurations to `auto`; preserve existing model selections without silent migration
- Permit custom model IDs during setup and fetch live available model IDs for the options selector

## Testing

Before submitting a PR:

1. Run `python3 -m unittest discover -s tests -v`
2. Check linting and formatting; hassfest, HACS validation, and CodeQL run through the workflows in `.github/workflows/`
3. Test setup and options flows in a Home Assistant instance
4. Test conversation agent functionality and error handling
5. Verify new configurations default to `auto`, existing model selections remain unchanged, and **Configure** offers live supported model IDs

### Manual Home Assistant MCP Check

Use a current **official Home Assistant Container** or Home Assistant OS instance. The integration's minimum Home Assistant version is 2025.2.4; the older 2024 development baseline has no built-in MCP server and cannot validate this feature.

The upgrade validation environment is **official Home Assistant Container 2026.9.1**, running under Docker Engine in Ubuntu WSL2. The built add-on image runs as a normal external CLI server. Home Assistant Container has no Supervisor, so this environment does **not** validate Home Assistant OS or the full Supervisor add-on lifecycle (installation, updates, and managed startup). Record actual checks and results separately; the environment description is not a test-pass claim.

1. Follow the [README MCP setup](README.md#mcp-configuration): add **Model Context Protocol Server**, enable its **Assist API**, and expose a safe input boolean helper to Assist.
2. Use two separate credentials: a GitHub fine-grained PAT with **Account permissions → Copilot Requests → Read and write**, and a Home Assistant long-lived token in the MCP `Authorization: Bearer ...` header. Classic GitHub PATs are not the supported fallback.
3. Configure MCP in the **integration's MCP field**, including when testing through the bridge. Use `http://homeassistant:8123/api/mcp` from the bridge, or an address reachable from the CLI runtime for a separate container deployment. No third-party MCP server or proxy is required.
4. In both setup and options flows, test inline JSON and a Home Assistant-readable file path, both with and without the optional `@` prefix. Confirm malformed JSON, unreadable paths, and invalid server definitions are rejected, with file I/O off the event loop.
5. Ask the agent to turn the test helper on and off. Confirm the actual entity state changes after each request; text claiming success is not sufficient.
6. Check explicit tool allowlists, denial of unconfigured MCP servers/tools, and disabled built-in CLI tools. Confirm add-on-only MCP configuration does not implicitly authorize tools.
7. Verify remote mode does not attempt a local runtime download. For local mode, test the SDK-managed runtime when no CLI executable is preinstalled or explicitly configured.
8. Use `auto` for a new conversation setup. If an older selection such as `gpt-4.1` returns `Model not available`, choose a live supported model through **Configure** and repeat the conversation and entity-state checks.

Record the Home Assistant, SDK, CLI, and add-on versions and the actual results in the PR. Redact credentials and authorization headers from all diagnostic output.

## Any Contributions You Make Will Be Under the GNU GPLv3

In short, when you submit code changes, your submissions are understood to be under the same [GNU GPLv3](https://choosealicense.com/licenses/gpl-3.0/) that covers the project.

## Report Bugs Using GitHub's [Issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose).

## Write Great Bug Reports

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Include Home Assistant version
  - Include integration version
  - Include relevant logs from `Settings` → `System` → `Logs`
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## Feature Requests

For feature requests, please:

- Check if the feature already exists
- Describe the use case clearly
- Explain why this would be useful to others
- Consider if it aligns with the integration's goals

## Documentation

When contributing:

- Update `README.md` for user-facing changes
- Update this guide for contributing/development documentation changes
- Update `addon/CHANGELOG.md` when changing the bridge add-on
- Update translations in `translations/en.json`
- Add code comments for complex logic

## License

By contributing, you agree that your contributions will be licensed under the GNU GPLv3.
