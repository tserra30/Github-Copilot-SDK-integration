"""Constants for github_copilot."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "github_copilot"
ATTRIBUTION = "Powered by GitHub Copilot SDK"

# Configuration constants
CONF_API_TOKEN = "api_token"  # noqa: S105
CONF_MODEL = "model"
CONF_CLI_URL = "cli_url"

# Default values
DEFAULT_MODEL = "gpt-4o"
DEFAULT_CLI_URL = ""

# Supported models
SUPPORTED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4.1",
    "gpt-3.5-turbo",
    "gpt-5",
    "o3-mini",
    "o1",
    "o1-mini",
    "claude-3-5-sonnet",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "claude-opus-4.6",
]

# Map of legacy model IDs (stored in old config entries) to current model IDs.
# Used to migrate existing entries that stored model values which are no
# longer present in SUPPORTED_MODELS without requiring a full config-entry
# version migration.
LEGACY_MODEL_MAP: dict[str, str] = {
    "claude-3.5-sonnet": "claude-3-5-sonnet",
    "claude-3.7-sonnet": "claude-3-5-sonnet",
}
