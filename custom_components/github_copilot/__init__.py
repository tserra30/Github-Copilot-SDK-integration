"""
Custom integration to integrate GitHub Copilot with Home Assistant.

For more details about this integration, please refer to
https://github.com/tserra30/Github-Copilot-SDK-integration
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import GitHubCopilotApiClient
from .const import (
    CONF_API_TOKEN,
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    LOGGER,
)
from .coordinator import GitHubCopilotDataUpdateCoordinator
from .data import GitHubCopilotData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import GitHubCopilotConfigEntry

PLATFORMS: list[Platform] = [
    Platform.CONVERSATION,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = GitHubCopilotDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(hours=1),
    )
    entry.runtime_data = GitHubCopilotData(
        client=GitHubCopilotApiClient(
            api_token=entry.data[CONF_API_TOKEN],
            model=entry.data.get(CONF_MODEL, DEFAULT_MODEL),
            max_tokens=entry.data.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
            temperature=entry.data.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
