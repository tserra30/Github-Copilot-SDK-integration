"""Adds config flow for copilot_assistant."""

from __future__ import annotations

from typing import Any

import copilot
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import CONF_ACCESS_TOKEN, DOMAIN, LOGGER


class CopilotAssistantFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GitHub Copilot SDK."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                # Validate that the token works by trying to start a client
                await self._test_token(user_input[CONF_ACCESS_TOKEN])

                # Set a unique ID to prevent multiple instances
                await self.async_set_unique_id("copilot_assistant")
                self._abort_if_unique_id_configured()

                # Create the config entry
                return self.async_create_entry(
                    title="GitHub Copilot SDK",
                    data=user_input,
                )
            except ConnectionError:
                LOGGER.error("Failed to connect to GitHub Copilot CLI")
                errors["base"] = "connection"
            except PermissionError:
                LOGGER.error("Authentication failed with GitHub Copilot")
                errors["base"] = "auth"
            except Exception as exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error during setup: %s", exception)
                errors["base"] = "unknown"

        # Show the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "documentation_url": "https://github.com/tserra30/Github-Copilot-SDK-integration",
            },
        )

    async def _test_token(self, access_token: str) -> None:
        """Validate the access token by starting a client."""
        client = None
        try:
            # Try to initialize and start the client
            client = copilot.CopilotClient({"github_token": access_token})
            await client.start()

            # Check auth status
            auth_status = await client.get_auth_status()
            if not auth_status.isAuthenticated:
                msg = "Copilot CLI is not authenticated"
                raise PermissionError(msg)

        finally:
            # Always clean up the test client
            if client:
                await client.stop()
