"""Constants for github_copilot."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "github_copilot"
ATTRIBUTION = "Powered by GitHub Copilot"

# Configuration constants
CONF_API_TOKEN = "api_token"  # noqa: S105
CONF_MODEL = "model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"

# Default values
DEFAULT_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7

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

# Reasoning models that don't support temperature parameter
# and use max_completion_tokens instead of max_tokens
REASONING_MODELS = {"o1", "o1-mini", "o3-mini"}

# Conversation constants
MAX_HISTORY_MESSAGES = 10
