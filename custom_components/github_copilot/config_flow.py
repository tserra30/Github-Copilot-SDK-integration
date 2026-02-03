"""Adds config flow for GitHub Copilot."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    GitHubCopilotApiClient,
    GitHubCopilotApiClientAuthenticationError,
    GitHubCopilotApiClientCommunicationError,
    GitHubCopilotApiClientError,
)
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
                    max_tokens=user_input.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                    temperature=user_input.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
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
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=DEFAULT_MAX_TOKENS,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=100,
                            max=4000,
                            step=100,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=DEFAULT_TEMPERATURE,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=2,
                            step=0.1,
                            mode=selector.NumberSelectorMode.SLIDER,
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
        max_tokens: int,
        temperature: float,
    ) -> None:
        """Validate credentials."""
        client = GitHubCopilotApiClient(
            api_token=api_token,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            session=async_get_clientsession(self.hass),
        )
        await client.async_test_connection()
