"""Custom types for github_copilot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import GitHubCopilotApiClient
    from .coordinator import GitHubCopilotDataUpdateCoordinator


type GitHubCopilotConfigEntry = ConfigEntry[GitHubCopilotData]


@dataclass
class GitHubCopilotData:
    """Data for the GitHub Copilot integration."""

    client: GitHubCopilotApiClient
    coordinator: GitHubCopilotDataUpdateCoordinator
    integration: Integration
