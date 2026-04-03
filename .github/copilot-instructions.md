# GitHub Copilot Instructions for GitHub Copilot Home Assistant Integration

## Project Overview

This repository contains a Home Assistant custom integration that brings GitHub Copilot AI capabilities to Home Assistant. It enables voice assistants and AI-powered tasks by implementing a conversation agent powered by the GitHub Copilot SDK.

## Technology Stack

- **Platform**: Home Assistant Custom Integration
- **Language**: Python 3.11+
- **Key Dependencies**:
  - `homeassistant` - Core Home Assistant framework
  - `github-copilot-sdk` - Copilot SDK client library (uses Copilot CLI runtime)
- **Development Tools**:
  - Ruff for linting (configured in `.ruff.toml`)
  - Dev container support (`.devcontainer.json`)

## Code Style and Standards

### Python Standards
- Use type hints with `from __future__ import annotations`
- All I/O operations must be async/await
- Follow Home Assistant coding conventions
- Use Ruff for linting: `ruff check custom_components/github_copilot/`
- Auto-fix issues with: `ruff check --fix custom_components/github_copilot/`

### Naming Conventions
- Use descriptive variable and function names
- Class names: PascalCase
- Functions and variables: snake_case
- Constants: UPPER_SNAKE_CASE

### Documentation
- Add docstrings to all public functions and classes
- Update README.md for user-facing changes
- Keep README.md and CONTRIBUTING.md aligned for technical documentation
- Keep code comments minimal but meaningful
- **Maintain addon/CHANGELOG.md** when making changes to the bridge add-on (Dockerfile, run.sh, config.yaml, build.yaml)
- Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format for changelog entries

## Project Structure

```
custom_components/github_copilot/
├── __init__.py           # Integration entry point
├── api.py                # GitHub Copilot SDK client
├── config_flow.py        # Configuration UI flow
├── conversation.py       # Conversation agent implementation
├── coordinator.py        # Data update coordinator
├── const.py              # Constants and configuration
└── data.py               # Data models

addon/                    # GitHub Copilot Bridge Add-on
├── Dockerfile            # Container image definition with Copilot CLI
├── config.yaml           # Add-on metadata and configuration schema
├── run.sh                # Server startup script with auth and retry logic
├── build.yaml            # Multi-arch build configuration
└── CHANGELOG.md          # Add-on version history and changes
```

## Key Components

### SDK Client (`api.py`)
- All methods should be async
- Use the GitHub Copilot SDK client
- Implement proper error handling with custom exceptions
- Include connection testing in `async_test_connection()`

### Conversation Agent (`conversation.py`)
- Extends Home Assistant's `ConversationEntity`
- Implements `async_process()` for message handling
- Maintains conversation history within sessions
- Handles errors gracefully with user-friendly messages

### Configuration Flow (`config_flow.py`)
- Validates credentials during setup
- Provides clear error messages for users
- Supports optional configuration parameters (model, cli_url)
- Follows Home Assistant's config flow patterns
- **cli_url parameter**: Enables connection to remote Copilot CLI server (bridge add-on)
- **Mutual exclusion**: When `cli_url` is provided, `github_token` is NOT passed to SDK (remote server handles auth)

### Bridge Add-on (`addon/`)
- **Purpose**: Runs GitHub Copilot CLI as a headless server for Home Assistant OS users
- **Dockerfile**:
  - Uses Debian Bullseye base for native glibc support (required by Copilot CLI)
  - Pins Copilot CLI version (currently v1.0.13) with SHA256 verification
  - Supports amd64 and aarch64 architectures
- **run.sh**:
  - Authenticates CLI via GH_TOKEN environment variable
  - Implements feature detection for optional CLI flags (--bind, --no-auto-update, --log-level)
  - Includes retry mechanism (up to 5 attempts with 5-second delays)
  - Hardened auth probe with timeout protection
- **Current version**: v3.8.3
- **Server port**: 8000 (internal Supervisor network only)
- **When to update**: Bump version in `config.yaml` when making significant changes to Dockerfile or run.sh

## Recent Important Changes (March-April 2026)

### SDK Version and HA OS Compatibility (Current PR)
- **Integration**: Uses github-copilot-sdk==0.1.32 from PyPI (standard installation)
- **HA OS limitation**: SDK 0.1.23+ only ship manylinux_2_28 wheels requiring glibc ≥ 2.28; Home Assistant OS cannot install these
- **Workaround for HA OS**: Manually install `github-copilot-sdk==0.1.22` (last version with universal py3-none-any wheels)
- **Protocol note**: Stock SDK 0.1.22 supports protocol v2 only; CLI v1.0.13 uses protocol v3. Do **not** assume stock 0.1.22 auto-negotiates v3.
- **Patched wheel**: A patched 0.1.22 wheel with protocol v3 support can be built via `.github/workflows/build-sdk.yml`

### Protocol v3 Support (PR #105)
- **Integration**: Updated github-copilot-sdk from 0.1.22 to 0.1.32
- **Add-on**: Updated Copilot CLI from v1.0.9 to v1.0.13
- **Impact**: SDK 0.1.32 natively supports protocol v3; CLI v1.0.13 uses protocol v3
- **Backward compatibility**: Both SDK and CLI support protocol v2

### CLI URL and Token Mutual Exclusion (PR #103)
- **Bug fixed**: SDK raised ValueError when both `github_token` and `cli_url` were provided
- **Solution**: `client_options` now uses mutual exclusion
  - Remote mode (cli_url): Server manages own auth, no token passed to SDK
  - Local mode (no cli_url): Token required and passed to SDK
- **Config flow**: Token is now optional when using bridge add-on
- **Impact**: Bridge add-on users no longer hit "Invalid Copilot client configuration" error

### Bridge Add-on Stability Improvements (PR #97)
- Enhanced authentication probe with timeout protection
- Improved feature detection for CLI flags across versions
- Better error handling and retry logic

### Base Image Migration (PR #74, #69)
- Migrated from Alpine (musl) to Debian Bullseye (glibc)
- **Reason**: Copilot CLI requires glibc, Alpine caused crashes
- **Result**: Improved stability and native binary support

### Home Assistant OS Compatibility (PR #82, #98)
- github-copilot-sdk 0.1.22 is last version with universal py3-none-any wheels
- Versions 0.1.23+ use manylinux wheels not recognized by HA OS pip
- Bridge add-on is the recommended solution for HA OS users

## Development Workflow

### Setup
1. Use the provided dev container for consistent environment:
   - Image: `mcr.microsoft.com/devcontainers/python:3.13`
   - Auto-runs: `scripts/setup` post-create (installs dependencies)
   - Port 8123 forwarded for Home Assistant access
2. Manual setup: `python3 -m pip install -r requirements.txt` (takes ~60-90 seconds)
3. Configuration is in `config/configuration.yaml`
4. Test changes in the standalone Home Assistant instance

### Build and Validation Commands

**IMPORTANT: Always run commands in this exact order to avoid errors:**

1. **Install dependencies** (required first):
   ```bash
   python3 -m pip install -r requirements.txt
   ```
   - Takes 60-90 seconds on first run
   - Required before any other commands
   - Run from repository root

2. **Lint code** (required before commits):
   ```bash
   python3 -m ruff check .
   ```
   - Takes 1-2 seconds
   - Must pass with no errors before committing
   - Auto-fix with: `python3 -m ruff check --fix .`

3. **Check formatting** (required before commits):
   ```bash
   python3 -m ruff format . --check
   ```
   - Takes <1 second
   - Must show "files already formatted"
   - Auto-fix with: `python3 -m ruff format .`

4. **Run Home Assistant validation** (CI requirement):
   - Hassfest validation checks integration manifest, structure, and dependencies
   - HACS validation ensures repository meets HACS requirements
   - These run automatically in CI - no local command available

### CI/CD Workflows

The repository uses three GitHub Actions workflows:

1. **Lint workflow** (`.github/workflows/lint.yml`):
   - Triggers: Push/PR to main branch
   - Python version: 3.13.2
   - Checks: `ruff check .` and `ruff format . --check`
   - Must pass before merge

2. **Validate workflow** (`.github/workflows/validate.yml`):
   - Triggers: Push/PR to main, daily schedule, manual
   - Runs hassfest validation (Home Assistant structure check)
   - Runs HACS validation (custom integration requirements)
   - Must pass before merge

3. **CodeQL workflow** (`.github/workflows/codeql.yml`):
   - Runs security analysis
   - Scans for vulnerabilities

### Before Committing - Required Checks
1. Run linter: `python3 -m ruff check .` (must show "All checks passed!")
2. Check formatting: `python3 -m ruff format . --check` (must show "files already formatted")
3. Test in a Home Assistant instance (manual testing)
4. Verify configuration flow works
5. Test conversation agent functionality
6. Check error handling

### Testing Guidelines
- **No automated tests exist** - all testing is manual
- Test the integration in a real Home Assistant environment
- Verify all user-facing features work correctly
- Test error conditions and edge cases
- Ensure API rate limiting is handled properly
- Test with different models (GPT-4o, Claude 3.5 Sonnet, etc.)

## Common Patterns

### Async Operations
```python
from __future__ import annotations

import copilot


class GitHubCopilotApiClient:
    def __init__(self, client_options: dict[str, str], ...) -> None:
        self._client = copilot.CopilotClient(client_options)

    async def async_test_connection(self) -> bool:
        await self._client.start()
        return True
```

### Error Handling
```python
from .api import (
    GitHubCopilotApiClientError,
    GitHubCopilotApiClientAuthenticationError,
    GitHubCopilotApiClientCommunicationError,
)

try:
    result = await api_call()
except GitHubCopilotApiClientAuthenticationError as exception:
    LOGGER.warning(exception)
    errors["base"] = "auth"
except GitHubCopilotApiClientCommunicationError as exception:
    LOGGER.error(exception)
    errors["base"] = "connection"
except GitHubCopilotApiClientError as exception:
    LOGGER.exception(exception)
    errors["base"] = "unknown"
```

### Configuration Validation
```python
async def async_step_user(self, user_input=None):
    """Handle user step."""
    _errors = {}
    if user_input is not None:
        try:
            await self._test_credentials(
                api_token=user_input[CONF_API_TOKEN],
                model=user_input.get(CONF_MODEL, DEFAULT_MODEL),
            )
        except GitHubCopilotApiClientAuthenticationError as exception:
            LOGGER.warning(exception)
            _errors["base"] = "auth"
        except GitHubCopilotApiClientCommunicationError as exception:
            LOGGER.error(exception)
            _errors["base"] = "connection"
```

## Important Notes

- This integration uses the GitHub Copilot SDK, not a raw API mimic
- Supports multiple models: GPT-4o, GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, o3-mini, o1, o1-mini, Claude 3.5 Sonnet
- Conversation history is stored in memory (not persisted)
- API rate limits must be respected
- All user data sent to GitHub Copilot follows GitHub's privacy policy

## Feature Development

When adding new features:
1. Check if it aligns with Home Assistant's conversation agent framework
2. Ensure backward compatibility with existing configurations
3. Add appropriate error handling
4. Update documentation (README.md, CONTRIBUTING.md)
5. Consider API rate limits and token usage

## Security Considerations

- Never commit API tokens or credentials
- Validate all user inputs in config flow
- Handle API errors gracefully without exposing sensitive data
- Follow Home Assistant's security best practices
- Keep dependencies up to date

## Common Issues and Workarounds

### Copilot CLI Not Found
- **Issue**: Integration fails with "Unable to connect to Copilot CLI"
- **Cause**: GitHub Copilot CLI not installed or not in PATH
- **Solution**:
  1. Install CLI from https://docs.github.com/copilot/cli
  2. Ensure it's executable and in PATH: `which copilot` or `copilot --version`
  3. Authenticate: `copilot auth login`
  4. For Home Assistant OS: CLI must be in Core container, not SSH add-on
  5. Set `COPILOT_CLI_PATH` env var if CLI is in non-standard location

### Home Assistant OS Specific Issues
- **Issue**: CLI works in SSH add-on but not in integration
- **Cause**: SSH add-on is separate from Core container
- **Solution**: Install CLI inside Core container (`docker exec -it homeassistant /bin/sh`)
- Persist auth with: `mkdir -p /config/.gh_config && export GH_CONFIG_DIR=/config/.gh_config`
- Use automation to reinstall CLI on boot (example in README.md)

### Import/Module Errors
- **Issue**: `ModuleNotFoundError` or import errors
- **Cause**: Dependencies not installed
- **Solution**: Run `python3 -m pip install -r requirements.txt` (takes 60-90 seconds)

### Ruff Command Not Found
- **Issue**: `bash: ruff: command not found`
- **Cause**: Ruff not installed or not using python module
- **Solution**: Use `python3 -m ruff` instead of `ruff` command

## File Locations

### Root Directory Files
- `.ruff.toml` - Ruff linter configuration
- `requirements.txt` - Python dependencies (colorlog, github-copilot-sdk==0.1.32, homeassistant==2024.12.3, ruff==0.15.8)
- `hacs.json` - HACS integration metadata
- `.devcontainer.json` - Dev container configuration
- `README.md` - User documentation
- `CONTRIBUTING.md` - Contribution guidelines
- `SECURITY.md` - Security policy

### Add-on Directory Files
- `addon/Dockerfile` - Container image with Copilot CLI v1.0.13
- `addon/config.yaml` - Add-on metadata, version v3.8.3
- `addon/run.sh` - Server startup script with auth and retry logic
- `addon/build.yaml` - Multi-architecture build configuration
- `addon/CHANGELOG.md` - Add-on version history (maintain when updating add-on)

### GitHub Workflows
- `.github/workflows/lint.yml` - Linting checks (ruff)
- `.github/workflows/validate.yml` - Hassfest and HACS validation
- `.github/workflows/codeql.yml` - Security scanning

### Scripts
- `scripts/setup` - Install dependencies (`python3 -m pip install --requirement requirements.txt`)
- `scripts/lint` - Format and fix code (`ruff format . && ruff check . --fix`) - Note: This script uses `ruff` directly as it's in the dev environment PATH

## Resources

- [Home Assistant Developer Documentation](https://developers.home-assistant.io/)
- [Integration Blueprint](https://github.com/ludeeus/integration_blueprint)
- Repository issues: https://github.com/tserra30/Github-Copilot-SDK-integration/issues
- Contributing guidelines: See CONTRIBUTING.md

## Instructions for Coding Agents

Always check documentation surrounding this repo.
Make sure to check all files before working and after.

When working with this codebase:
1. Always run `python3 -m pip install -r requirements.txt` first if starting fresh
2. Always lint with `python3 -m ruff check .` before committing
3. Use `python3 -m ruff` not `ruff` command directly (except in scripts/lint which uses `ruff` directly)
4. All code must be async - use `async`/`await` for I/O operations
5. Follow Home Assistant patterns - check existing files for examples
6. Test manually in Home Assistant - no automated tests exist
