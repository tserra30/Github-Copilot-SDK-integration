"""DataUpdateCoordinator for github_copilot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from .data import GitHubCopilotConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class GitHubCopilotDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: GitHubCopilotConfigEntry

    async def _async_update_data(self) -> Any:
        """
        Update data via library.

        For conversation agents, we don't need to poll for data.
        Conversation processing is event-driven via the conversation entity.
        """
        return {}
