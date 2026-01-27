# GitHub Copilot Instructions for GitHub Copilot Home Assistant Integration

## Project Overview

This repository contains a Home Assistant custom integration that brings GitHub Copilot AI capabilities to Home Assistant. It enables voice assistants and AI-powered tasks by implementing a conversation agent powered by GitHub Copilot API.

## Technology Stack

- **Platform**: Home Assistant Custom Integration
- **Language**: Python 3.11+
- **Key Dependencies**: 
  - `homeassistant` - Core Home Assistant framework
  - `aiohttp` - Async HTTP client for API calls
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
- Update agents.md for detailed technical documentation
- Keep code comments minimal but meaningful

## Project Structure

```
custom_components/github_copilot/
├── __init__.py           # Integration entry point
├── api.py                # GitHub Copilot API client
├── config_flow.py        # Configuration UI flow
├── conversation.py       # Conversation agent implementation
├── coordinator.py        # Data update coordinator
├── const.py              # Constants and configuration
└── data.py               # Data models
```

## Key Components

### API Client (`api.py`)
- All methods should be async
- Use aiohttp for HTTP requests
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
- Supports optional configuration parameters (model, temperature, max_tokens)
- Follows Home Assistant's config flow patterns

## Development Workflow

### Setup
1. Use the provided dev container for consistent environment
2. Configuration is in `config/configuration.yaml`
3. Test changes in the standalone Home Assistant instance

### Before Committing
1. Run linter: `ruff check custom_components/github_copilot/`
2. Test in a Home Assistant instance
3. Verify configuration flow works
4. Test conversation agent functionality
5. Check error handling

### Testing Guidelines
- Test the integration in a real Home Assistant environment
- Verify all user-facing features work correctly
- Test error conditions and edge cases
- Ensure API rate limiting is handled properly

## Common Patterns

### Async Operations
```python
from __future__ import annotations

# API client uses a shared session passed to the constructor
class GitHubCopilotApiClient:
    def __init__(self, api_token: str, session: aiohttp.ClientSession, ...) -> None:
        self._session = session
        
    async def _api_wrapper(self, method: str, url: str, data: dict | None = None) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(30):
                response = await self._session.request(method=method, url=url, json=data)
                return await response.json()
        except TimeoutError as exception:
            raise GitHubCopilotApiClientCommunicationError(...) from exception
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

- This integration uses GitHub Copilot API, not standard OpenAI API
- Supports multiple models: GPT-4o, GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, Claude 3.7 Sonnet
- Conversation history is stored in memory (not persisted)
- API rate limits must be respected
- All user data sent to GitHub Copilot API follows GitHub's privacy policy

## Feature Development

When adding new features:
1. Check if it aligns with Home Assistant's conversation agent framework
2. Ensure backward compatibility with existing configurations
3. Add appropriate error handling
4. Update documentation (README.md, agents.md)
5. Consider API rate limits and token usage

## Security Considerations

- Never commit API tokens or credentials
- Validate all user inputs in config flow
- Handle API errors gracefully without exposing sensitive data
- Follow Home Assistant's security best practices
- Keep dependencies up to date

## Resources

- [Home Assistant Developer Documentation](https://developers.home-assistant.io/)
- [Integration Blueprint](https://github.com/ludeeus/integration_blueprint)
- Repository issues: https://github.com/tserra30/Github-Copilot-SDK-integration/issues
- Contributing guidelines: See CONTRIBUTING.md
