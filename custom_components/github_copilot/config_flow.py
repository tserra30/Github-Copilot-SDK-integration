"""Adds config flow for GitHub Copilot."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

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
    CONF_CLI_URL,
    CONF_MODEL,
    DEFAULT_CLI_URL,
    DEFAULT_MODEL,
    DOMAIN,
    LEGACY_MODEL_MAP,
    LOGGER,
    SUPPORTED_MODELS,
)


def _validate_cli_url(cli_url: str) -> bool:
    """Return True if cli_url is a valid http/https URL, False otherwise."""
    parsed = urlparse(cli_url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


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
            cli_url = user_input.get(CONF_CLI_URL, DEFAULT_CLI_URL).strip()
            api_token = user_input.get(CONF_API_TOKEN, "").strip()

            # Validate the CLI URL format if provided
            if cli_url and not _validate_cli_url(cli_url):
                _errors[CONF_CLI_URL] = "invalid_url"
            elif not cli_url and not api_token:
                # Local mode requires a GitHub token; remote mode does not.
                _errors[CONF_API_TOKEN] = "token_required"

            if not _errors:
                try:
                    LOGGER.debug(
                        "Testing GitHub Copilot credentials with model '%s'",
                        model,
                    )
                    await self._test_credentials(
                        api_token=api_token,
                        model=model,
                        cli_url=cli_url,
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
                        "Unexpected error during GitHub Copilot setup: %s - %s",
                        type(exception).__name__,
                        str(exception),
                    )
                    _errors["base"] = "unknown"
                except Exception as exception:  # noqa: BLE001
                    LOGGER.exception(
                        "Unexpected error in config flow: %s - %s",
                        type(exception).__name__,
                        str(exception),
                    )
                    _errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id("github_copilot")
                    self._abort_if_unique_id_configured()
                    LOGGER.info(
                        "GitHub Copilot integration configured with model '%s'",
                        model,
                    )
                    # Normalize the cli_url to the stripped value before persisting.
                    # In remote mode, don't persist the token (server handles auth).
                    data = {**user_input, CONF_CLI_URL: cli_url}
                    if cli_url:
                        data.pop(CONF_API_TOKEN, None)
                    return self.async_create_entry(
                        title="GitHub Copilot",
                        data=data,
                    )

        try:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_API_TOKEN): selector.TextSelector(
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
                            CONF_CLI_URL,
                            default=DEFAULT_CLI_URL,
                        ): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.URL,
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
                "Failed to render config flow form: %s - %s. "
                "This may indicate a dependency or import issue.",
                type(exception).__name__,
                str(exception),
            )
            # Return error form with minimal schema to avoid further errors
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_API_TOKEN): str,
                    }
                ),
                errors={"base": "unknown"},
            )

    async def _test_credentials(
        self,
        api_token: str,
        model: str,
        cli_url: str = DEFAULT_CLI_URL,
    ) -> None:
        """Validate credentials."""
        client_options: dict[str, Any] = {}
        if cli_url:
            # Remote CLI mode: the external server manages its own authentication,
            # so github_token must NOT be passed (SDK enforces this constraint).
            client_options["cli_url"] = cli_url
        else:
            # Local CLI mode: authenticate using the provided GitHub token.
            client_options["github_token"] = api_token
        client = GitHubCopilotApiClient(
            model=model,
            client_options=client_options,
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
                "Unexpected exception during credential test: %s - %s. "
                "Full details in traceback.",
                type(exception).__name__,
                str(exception),
            )
            msg = (
                f"Unexpected error during credential validation: "
                f"{type(exception).__name__}: {exception}"
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
        _errors: dict[str, str] = {}
        if user_input is not None:
            cli_url = user_input.get(CONF_CLI_URL, DEFAULT_CLI_URL).strip()

            # Apply the same http/https validation as the initial config flow
            if cli_url and not _validate_cli_url(cli_url):
                _errors[CONF_CLI_URL] = "invalid_url"

            if not _errors:
                # Update the config entry with the normalized model and CLI URL
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_CLI_URL: cli_url,
                    },
                )
                return self.async_create_entry(title="", data={})

        # Get current model from config entry, normalizing any legacy IDs.
        current_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        current_model = LEGACY_MODEL_MAP.get(current_model, current_model)

        # Get current CLI URL from config entry
        current_cli_url = self.config_entry.data.get(CONF_CLI_URL, DEFAULT_CLI_URL)

        # Try to fetch the available models dynamically; fall back to the
        # hardcoded list if the API call fails or runtime_data is unavailable.
        available_models = SUPPORTED_MODELS
        try:
            available_models = list(
                await self.config_entry.runtime_data.client.async_available_models()
            )
        except (GitHubCopilotApiClientError, AttributeError):
            LOGGER.debug(
                "Could not fetch dynamic model list; using built-in fallback.",
                exc_info=True,
            )

        # Ensure the currently selected model is always present in the list so
        # the dropdown does not show a blank/invalid selection.
        if current_model not in available_models:
            available_models = [current_model, *available_models]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=current_model,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=available_models,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Optional(
                        CONF_CLI_URL,
                        default=current_cli_url,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.URL,
                        ),
                    ),
                }
            ),
            errors=_errors,
        )
