"""
Custom integration to integrate GitHub Copilot SDK with Home Assistant.

For more details about this integration, please refer to
https://github.com/tserra30/Github-Copilot-SDK-integration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import copilot

from .const import CONF_ACCESS_TOKEN, DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    try:
        # Get the access token from config entry
        access_token = entry.data[CONF_ACCESS_TOKEN]

        # Initialize the Copilot client
        client = copilot.CopilotClient({"github_token": access_token})

        # Start the client (as seen in SDK docs)
        await client.start()

        # Store the client in hass.data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = client

        LOGGER.info("GitHub Copilot SDK integration setup completed successfully")
        return True  # noqa: TRY300
    except Exception as err:
        LOGGER.error(
            "Failed to set up GitHub Copilot SDK integration: %s",
            type(err).__name__,
        )
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    try:
        # Get the client from hass.data
        client = hass.data[DOMAIN].pop(entry.entry_id, None)

        if client:
            # Stop the client
            await client.stop()

        LOGGER.info("GitHub Copilot SDK integration unloaded successfully")
        return True  # noqa: TRY300
    except Exception as err:  # noqa: BLE001
        LOGGER.error(
            "Failed to unload GitHub Copilot SDK integration: %s",
            type(err).__name__,
        )
        return False
