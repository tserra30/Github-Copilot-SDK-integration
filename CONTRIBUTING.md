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
3. Make sure your code lints with `ruff` (run `python3 -m ruff check .`).
4. Test your contribution.
5. Issue that pull request!

## Development Environment

This integration is based on the [integration_blueprint template](https://github.com/ludeeus/integration_blueprint).

### Setup

1. Use the provided `.devcontainer.json` for Visual Studio Code development
2. The container includes a standalone Home Assistant instance
3. Configuration is in [`config/configuration.yaml`](./config/configuration.yaml)

### SDK Dependency

This integration uses a **patched `github-copilot-sdk 0.1.22+ha` wheel** bundled in `wheels/` for Home Assistant OS compatibility. The wheel is installed automatically from `manifest.json` — no manual steps are needed. If you need to rebuild it, run the `.github/workflows/build-sdk.yml` workflow (see `wheels/README.md` for details).

### Running the Linter

```bash
python3 -m ruff check .
```

### Auto-fixing Issues

```bash
python3 -m ruff check --fix .
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
- Use aiohttp for HTTP requests
- Implement connection testing in `async_test_connection()`

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

## Testing

Before submitting a PR:

1. Test the integration in a Home Assistant instance
2. Verify configuration flow works correctly
3. Test conversation agent functionality
4. Check error handling
5. Ensure all linting passes

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
- Update translations in `translations/en.json`
- Add code comments for complex logic

## License

By contributing, you agree that your contributions will be licensed under the GNU GPLv3.
