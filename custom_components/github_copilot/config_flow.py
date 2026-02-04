"""Adds config flow for GitHub Copilot."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .api import (
    GitHubCopilotApiClient,
    GitHubCopilotApiClientAuthenticationError,
    GitHubCopilotApiClientCommunicationError,
    GitHubCopilotApiClientError,
)
from .const import (
    CONF_API_TOKEN,
    CONF_MODEL,
    DEFAULT_MODEL,
    DOMAIN,
    LOGGER,
    SUPPORTED_MODELS,
)


class GitHubCopilotFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GitHub Copilot."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    api_token=user_input[CONF_API_TOKEN],
                    model=user_input.get(CONF_MODEL, DEFAULT_MODEL),
                )
            except GitHubCopilotApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except GitHubCopilotApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except GitHubCopilotApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id("github_copilot")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="GitHub Copilot",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Optional(
                        CONF_MODEL,
                        default=DEFAULT_MODEL,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SUPPORTED_MODELS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                },
            ),
            errors=_errors,
            description_placeholders={
                "documentation_url": "https://github.com/tserra30/Github-Copilot-SDK-integration",
            },
        )

    async def _test_credentials(
        self,
        api_token: str,
        model: str,
    ) -> None:
        """Validate credentials."""
        client = GitHubCopilotApiClient(
            model=model,
            client_options={"github_token": api_token},
        )
        try:
            await client.async_test_connection()
        finally:
            await client.async_close()
