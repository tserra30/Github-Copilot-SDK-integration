"""Constants for github_copilot."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "github_copilot"
ATTRIBUTION = "Powered by GitHub Copilot SDK"

# Configuration constants
CONF_API_TOKEN = "api_token"  # noqa: S105
CONF_MODEL = "model"

# Default values
DEFAULT_MODEL = "gpt-4o"

# Supported models
SUPPORTED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "o3-mini",
    "o1",
    "o1-mini",
    "claude-3.5-sonnet",
    "claude-3.7-sonnet",
]


# API constants
API_TIMEOUT = 30  # Timeout in seconds for API requests
