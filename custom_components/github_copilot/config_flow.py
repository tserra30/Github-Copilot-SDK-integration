"""Adds config flow for GitHub Copilot."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .auth import (
    DeviceCodeResponse,
    GitHubAuthDeniedError,
    GitHubAuthError,
    GitHubAuthTimeoutError,
    GitHubCopilotAuth,
    GitHubToken,
)
from .const import (
    CONF_GITHUB_TOKEN,
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

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._auth: GitHubCopilotAuth | None = None
        self._device_code_response: DeviceCodeResponse | None = None
        self._github_token: GitHubToken | None = None

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user.

        This step starts the OAuth device flow.
        """
        errors: dict[str, str] = {}

        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            # User clicked submit, start device flow
            try:
                session = async_create_clientsession(self.hass)
                self._auth = GitHubCopilotAuth(self.hass, session)
                self._device_code_response = await self._auth.start_device_flow()

                # Move to the authorization step
                return await self.async_step_authorize()

            except GitHubAuthError as err:
                LOGGER.error("Failed to start device flow: %s", err)
                errors["base"] = "device_flow_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/tserra30/Github-Copilot-SDK-integration"
            },
        )

    async def async_step_authorize(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the authorization step.

        Shows the user code and waits for authorization.
        """
        errors: dict[str, str] = {}

        if self._device_code_response is None or self._auth is None:
            return await self.async_step_user()

        if user_input is not None:
            # User clicked "I've authorized" - check for token
            try:
                # If we don't have a token yet, poll once more
                if self._github_token is None:
                    self._github_token = await self._auth.poll_for_token(
                        device_code=self._device_code_response.device_code,
                        interval=self._device_code_response.interval,
                        expires_in=30,  # Short timeout since user says they've authorized
                    )

                # Validate by getting a Copilot token
                await self._auth.get_copilot_token(self._github_token.access_token)

                # Success! Move to configuration step
                return await self.async_step_configure()

            except GitHubAuthTimeoutError:
                errors["base"] = "authorization_pending"
            except GitHubAuthDeniedError:
                errors["base"] = "authorization_denied"
            except GitHubAuthError as err:
                LOGGER.error("Authorization failed: %s", err)
                if "Copilot subscription" in str(err):
                    errors["base"] = "no_copilot_subscription"
                else:
                    errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "user_code": self._device_code_response.user_code,
                "verification_uri": self._device_code_response.verification_uri,
            },
        )

    async def async_step_configure(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the configuration step.

        Allows user to configure model and other settings.
        """
        if self._github_token is None:
            return await self.async_step_user()

        if user_input is not None:
            # Create the entry with the token and settings
            return self.async_create_entry(
                title="GitHub Copilot",
                data={
                    CONF_GITHUB_TOKEN: self._github_token.access_token,
                },
                options={
                    CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL),
                    CONF_MAX_TOKENS: user_input.get(
                        CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
                    ),
                    CONF_TEMPERATURE: user_input.get(
                        CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                    ),
                },
            )

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
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
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication when token expires."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                session = async_create_clientsession(self.hass)
                self._auth = GitHubCopilotAuth(self.hass, session)
                self._device_code_response = await self._auth.start_device_flow()
                return await self.async_step_reauth_authorize()
            except GitHubAuthError as err:
                LOGGER.error("Failed to start re-auth device flow: %s", err)
                errors["base"] = "device_flow_failed"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_reauth_authorize(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication authorization."""
        errors: dict[str, str] = {}

        if self._device_code_response is None or self._auth is None:
            return await self.async_step_reauth_confirm()

        if user_input is not None:
            try:
                if self._github_token is None:
                    self._github_token = await self._auth.poll_for_token(
                        device_code=self._device_code_response.device_code,
                        interval=self._device_code_response.interval,
                        expires_in=30,
                    )

                await self._auth.get_copilot_token(self._github_token.access_token)

                # Update the existing entry
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_GITHUB_TOKEN: self._github_token.access_token,
                    },
                )

            except GitHubAuthTimeoutError:
                errors["base"] = "authorization_pending"
            except GitHubAuthDeniedError:
                errors["base"] = "authorization_denied"
            except GitHubAuthError as err:
                LOGGER.error("Re-authorization failed: %s", err)
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="reauth_authorize",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "user_code": self._device_code_response.user_code,
                "verification_uri": self._device_code_response.verification_uri,
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GitHubCopilotOptionsFlowHandler:
        """Get the options flow for this handler."""
        return GitHubCopilotOptionsFlowHandler(config_entry)


class GitHubCopilotOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for GitHub Copilot."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values from options, falling back to data for migration
        current_model = self._config_entry.options.get(
            CONF_MODEL,
            self._config_entry.data.get(CONF_MODEL, DEFAULT_MODEL),
        )
        current_max_tokens = self._config_entry.options.get(
            CONF_MAX_TOKENS,
            self._config_entry.data.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
        )
        current_temperature = self._config_entry.options.get(
            CONF_TEMPERATURE,
            self._config_entry.data.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MODEL,
                        default=current_model,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SUPPORTED_MODELS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=current_max_tokens,
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
                        default=current_temperature,
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
        )
