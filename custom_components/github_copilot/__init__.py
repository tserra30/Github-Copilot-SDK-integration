"""
Custom integration to integrate GitHub Copilot with Home Assistant.

For more details about this integration, please refer to
https://github.com/tserra30/Github-Copilot-SDK-integration
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .api import GitHubCopilotApiClient
from .const import (
    CONF_API_TOKEN,
    CONF_CLI_URL,
    CONF_MODEL,
    DEFAULT_CLI_URL,
    DEFAULT_MODEL,
    DOMAIN,
    LEGACY_MODEL_MAP,
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
    try:
        coordinator = GitHubCopilotDataUpdateCoordinator(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        cli_url = entry.data.get(CONF_CLI_URL, DEFAULT_CLI_URL).strip()
        client_options: dict[str, str] = {"github_token": entry.data[CONF_API_TOKEN]}
        if cli_url:
            client_options["cli_url"] = cli_url

        # Normalize legacy model IDs (e.g. "claude-3.5-sonnet" → "claude-3-5-sonnet")
        # stored in config entries created before the model names were corrected.
        model = entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        if model in LEGACY_MODEL_MAP:
            new_model = LEGACY_MODEL_MAP[model]
            LOGGER.info(
                "Migrating stored model '%s' to '%s'",
                model,
                new_model,
            )
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_MODEL: new_model},
            )
            model = new_model

        entry.runtime_data = GitHubCopilotData(
            client=GitHubCopilotApiClient(
                model=model,
                client_options=client_options,
            ),
            integration=async_get_loaded_integration(hass, entry.domain),
            coordinator=coordinator,
        )

        # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
        await coordinator.async_config_entry_first_refresh()

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

        LOGGER.info("GitHub Copilot integration setup completed successfully")
        return True  # noqa: TRY300
    except Exception as err:
        # Don't log exception details to avoid exposing tokens
        # or sensitive config data
        LOGGER.error(
            "Failed to set up GitHub Copilot integration: %s",
            type(err).__name__,
        )
        raise


async def async_unload_entry(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.async_close()
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
