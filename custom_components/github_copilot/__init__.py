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
from .auth import GitHubCopilotAuth, GitHubToken
from .const import (
    CONF_API_TOKEN,
    CONF_GITHUB_TOKEN,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    session = async_get_clientsession(hass)

    # Create auth handler
    auth = GitHubCopilotAuth(hass, session)

    # Get the GitHub token - support both old and new config formats
    github_token = entry.data.get(CONF_GITHUB_TOKEN) or entry.data.get(CONF_API_TOKEN)

    if not github_token:
        LOGGER.error("No GitHub token found in configuration")
        return False

    # Set up the auth handler with the stored token
    auth.set_github_token(
        GitHubToken(
            access_token=github_token,
            token_type="bearer",
            scope="read:user",
        )
    )

    # Get settings from options (preferred) or data (fallback for migration)
    model = entry.options.get(CONF_MODEL) or entry.data.get(CONF_MODEL, DEFAULT_MODEL)
    max_tokens = entry.options.get(CONF_MAX_TOKENS) or entry.data.get(
        CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
    )
    temperature = entry.options.get(CONF_TEMPERATURE) or entry.data.get(
        CONF_TEMPERATURE, DEFAULT_TEMPERATURE
    )

    # Create coordinator
    coordinator = GitHubCopilotDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(hours=1),
    )

    # Create API client with auth handler
    client = GitHubCopilotApiClient(
        session=session,
        auth=auth,
        model=model,
        max_tokens=int(max_tokens),
        temperature=float(temperature),
    )

    # Store runtime data
    entry.runtime_data = GitHubCopilotData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
        auth=auth,
    )

    # First refresh of coordinator
    await coordinator.async_config_entry_first_refresh()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options changes
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_options_update_listener(
    hass: HomeAssistant,
    entry: GitHubCopilotConfigEntry,
) -> None:
    """Handle options update.

    Updates the API client settings when options change without reloading.
    """
    if entry.runtime_data and entry.runtime_data.client:
        # Update client settings with new options
        model = entry.options.get(CONF_MODEL, DEFAULT_MODEL)
        max_tokens = entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        temperature = entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)

        entry.runtime_data.client.update_settings(
            model=model,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
        )
        LOGGER.info(
            "Updated GitHub Copilot settings: model=%s, max_tokens=%s, temperature=%s",
            model,
            max_tokens,
            temperature,
        )


async def async_migrate_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: GitHubCopilotConfigEntry,
) -> bool:
    """Migrate old entry to new format."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Version 1 had api_token in data, we now use github_token
        # and move settings to options
        new_data = {}
        new_options = {}

        # Move token to new key
        if CONF_API_TOKEN in config_entry.data:
            new_data[CONF_GITHUB_TOKEN] = config_entry.data[CONF_API_TOKEN]

        # Move settings to options
        if CONF_MODEL in config_entry.data:
            new_options[CONF_MODEL] = config_entry.data[CONF_MODEL]
        if CONF_MAX_TOKENS in config_entry.data:
            new_options[CONF_MAX_TOKENS] = config_entry.data[CONF_MAX_TOKENS]
        if CONF_TEMPERATURE in config_entry.data:
            new_options[CONF_TEMPERATURE] = config_entry.data[CONF_TEMPERATURE]

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options=new_options,
            version=2,
        )

        LOGGER.info("Migration to version 2 successful")

    return True
