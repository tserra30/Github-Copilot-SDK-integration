"""Adds config flow for GitHub Copilot."""

from __future__ import annotations

from typing import Any

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

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GitHubCopilotOptionsFlow:
        """Get the options flow for this handler."""
        return GitHubCopilotOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            model = user_input.get(CONF_MODEL, DEFAULT_MODEL)
            try:
                LOGGER.debug(
                    "Testing GitHub Copilot credentials with model '%s'",
                    model,
                )
                await self._test_credentials(
                    api_token=user_input[CONF_API_TOKEN],
                    model=model,
                )
            except GitHubCopilotApiClientAuthenticationError as exception:
                LOGGER.warning(
                    "GitHub Copilot authentication failed: %s",
                    exception,
                )
                _errors["base"] = "auth"
            except GitHubCopilotApiClientCommunicationError as exception:
                LOGGER.error(
                    "Failed to connect to GitHub Copilot CLI: %s",
                    exception,
                )
                _errors["base"] = "connection"
            except GitHubCopilotApiClientError as exception:
                LOGGER.exception(
                    "Unexpected error during GitHub Copilot setup: %s",
                    exception,
                )
                _errors["base"] = "unknown"
            except Exception as exception:  # noqa: BLE001
                LOGGER.exception(
                    "Unexpected error in config flow: %s",
                    type(exception).__name__,
                )
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id("github_copilot")
                self._abort_if_unique_id_configured()
                LOGGER.info(
                    "GitHub Copilot integration configured with model '%s'",
                    model,
                )
                return self.async_create_entry(
                    title="GitHub Copilot",
                    data=user_input,
                )

        try:
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
        except Exception as exception:  # noqa: BLE001
            LOGGER.exception(
                "Failed to render config flow form: %s",
                type(exception).__name__,
            )
            # Return error form with minimal schema to avoid further errors
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_API_TOKEN): str,
                    }
                ),
                errors={"base": "unknown"},
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
        except (
            GitHubCopilotApiClientAuthenticationError,
            GitHubCopilotApiClientCommunicationError,
            GitHubCopilotApiClientError,
        ):
            # Re-raise our custom exceptions as-is
            raise
        except Exception as exception:
            # Wrap any unexpected exception
            LOGGER.exception(
                "Unexpected exception during credential test: %s",
                type(exception).__name__,
            )
            msg = (
                f"Unexpected error during credential validation: "
                f"{type(exception).__name__}"
            )
            raise GitHubCopilotApiClientError(msg) from exception
        finally:
            # Always clean up the client, even on exception
            await client.async_close()


class GitHubCopilotOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for GitHub Copilot integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            # Update the config entry with new model
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_MODEL: user_input[CONF_MODEL],
                },
            )
            return self.async_create_entry(title="", data={})

        # Get current model from config entry
        current_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=current_model,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SUPPORTED_MODELS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
        )
