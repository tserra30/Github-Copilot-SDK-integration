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
    GitHubCopilotApiClientReasoningError,
)
from .const import (
    CONF_API_TOKEN,
    CONF_CLI_URL,
    CONF_MCP_CONFIG,
    CONF_MODEL,
    CONF_REASONING_EFFORT,
    CONF_TIMEOUT,
    DEFAULT_CLI_URL,
    DEFAULT_MCP_CONFIG,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LEGACY_MODEL_MAP,
    LOGGER,
    SUPPORTED_MODELS,
)
from .mcp import async_load_mcp_config
from .reasoning import ReasoningCapabilities


def _validate_cli_url(cli_url: str) -> bool:
    """Return True if cli_url is a valid http/https URL, False otherwise."""
    parsed = urlparse(cli_url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


async def _async_validate_mcp_config(mcp_config: str) -> bool:
    """Return True if mcp_config is a valid MCP configuration string or file path."""
    try:
        await async_load_mcp_config(mcp_config)
    except ValueError:
        return False
    return True


def _client_for_config(
    data: dict[str, Any], reasoning_effort: str | None = None
) -> GitHubCopilotApiClient:
    """Use candidate connection settings for metadata and session validation."""
    cli_url = data.get(CONF_CLI_URL, DEFAULT_CLI_URL).strip()
    client_options = (
        {"cli_url": cli_url}
        if cli_url
        else {"github_token": data.get(CONF_API_TOKEN, "")}
    )
    return GitHubCopilotApiClient(
        model=data.get(CONF_MODEL, DEFAULT_MODEL),
        client_options=client_options,
        mcp_config=data.get(CONF_MCP_CONFIG, DEFAULT_MCP_CONFIG) or "",
        timeout=float(data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
        reasoning_effort=reasoning_effort,
    )


async def _async_reasoning_metadata(
    data: dict[str, Any],
) -> tuple[ReasoningCapabilities, str | None]:
    """Fetch metadata without keeping a client alive if a form is abandoned."""
    client = _client_for_config(data)
    try:
        try:
            capabilities = await client.async_reasoning_capabilities()
        finally:
            await client.async_close()
    except GitHubCopilotApiClientAuthenticationError:
        return ReasoningCapabilities(), "auth"
    except GitHubCopilotApiClientError:
        LOGGER.warning(
            "Could not fetch reasoning capabilities; only Model default "
            "can be selected until metadata is available."
        )
        return ReasoningCapabilities(), "reasoning_metadata_unavailable"
    return capabilities, None


def _reasoning_errors(
    capabilities: ReasoningCapabilities, selected: str
) -> dict[str, str]:
    """Do not silently replace an unsupported saved or submitted override."""
    if selected == DEFAULT_REASONING_EFFORT:
        return {}
    if not capabilities.known:
        return {CONF_REASONING_EFFORT: "reasoning_metadata_unavailable"}
    if selected not in capabilities.supported_efforts:
        return {CONF_REASONING_EFFORT: "unsupported_reasoning_effort"}
    return {}


def _reasoning_schema(capabilities: ReasoningCapabilities, selected: str) -> vol.Schema:
    """Show the selected model's levels and preserve an invalid saved selection."""
    choices = [DEFAULT_REASONING_EFFORT, *capabilities.supported_efforts]
    if selected not in choices:
        choices.append(selected)
    return vol.Schema(
        {
            vol.Required(
                CONF_REASONING_EFFORT, default=selected
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=choices,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_REASONING_EFFORT,
                )
            )
        }
    )


def _with_reasoning_choice(data: dict[str, Any], selected: str) -> dict[str, Any]:
    """Represent Model default by the absence of an override, not a fixed level."""
    data = dict(data)
    if selected == DEFAULT_REASONING_EFFORT:
        data.pop(CONF_REASONING_EFFORT, None)
    else:
        data[CONF_REASONING_EFFORT] = selected
    return data


class GitHubCopilotFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GitHub Copilot."""

    VERSION = 1
    _pending_data: dict[str, Any] | None = None
    _reasoning_capabilities = ReasoningCapabilities()
    _reasoning_metadata_error: str | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,  # noqa: ARG004
    ) -> GitHubCopilotOptionsFlow:
        """Get the options flow for this handler."""
        return GitHubCopilotOptionsFlow()

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
            mcp_config = user_input.get(CONF_MCP_CONFIG, DEFAULT_MCP_CONFIG) or ""

            # Validate the CLI URL format if provided
            if cli_url and not _validate_cli_url(cli_url):
                _errors[CONF_CLI_URL] = "invalid_url"
            elif not cli_url and not api_token:
                # Local mode requires a GitHub token; remote mode does not.
                _errors[CONF_API_TOKEN] = "token_required"

            # Validate MCP config if provided
            if mcp_config and not await _async_validate_mcp_config(mcp_config):
                _errors[CONF_MCP_CONFIG] = "invalid_mcp"

            if not _errors:
                self._pending_data = {
                    **user_input,
                    CONF_API_TOKEN: api_token,
                    CONF_MODEL: model,
                    CONF_CLI_URL: cli_url,
                    CONF_MCP_CONFIG: mcp_config,
                }
                result = await self.async_step_reasoning()
                if self._reasoning_metadata_error != "auth":
                    return result
                self._pending_data = None
                _errors["base"] = "auth"

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
                                custom_value=True,
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
                        vol.Optional(
                            CONF_MCP_CONFIG,
                            default=DEFAULT_MCP_CONFIG,
                        ): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.PASSWORD,
                            ),
                        ),
                    },
                ),
                errors=_errors,
                description_placeholders={
                    "documentation_url": "https://github.com/tserra30/Github-Copilot-SDK-integration",
                },
                last_step=False,
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

    async def async_step_reasoning(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose reasoning effort after the model and connection are known."""
        if self._pending_data is None:
            return await self.async_step_user()
        data = self._pending_data
        if user_input is None or not self._reasoning_capabilities.known:
            (
                self._reasoning_capabilities,
                self._reasoning_metadata_error,
            ) = await _async_reasoning_metadata(data)
        selected = (
            user_input[CONF_REASONING_EFFORT]
            if user_input is not None
            else data.get(CONF_REASONING_EFFORT) or DEFAULT_REASONING_EFFORT
        )
        errors = _reasoning_errors(self._reasoning_capabilities, selected)
        if user_input is not None and not errors:
            data = _with_reasoning_choice(data, selected)
            try:
                await self._test_credentials(
                    api_token=data.get(CONF_API_TOKEN, ""),
                    model=data[CONF_MODEL],
                    cli_url=data[CONF_CLI_URL],
                    mcp_config=data[CONF_MCP_CONFIG],
                    reasoning_effort=data.get(CONF_REASONING_EFFORT),
                )
            except GitHubCopilotApiClientAuthenticationError:
                errors["base"] = "auth"
            except GitHubCopilotApiClientCommunicationError:
                errors["base"] = "connection"
            except GitHubCopilotApiClientReasoningError:
                errors[CONF_REASONING_EFFORT] = "unsupported_reasoning_effort"
                self._reasoning_capabilities = ReasoningCapabilities()
            except GitHubCopilotApiClientError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id("github_copilot")
                self._abort_if_unique_id_configured()
                if data[CONF_CLI_URL]:
                    data.pop(CONF_API_TOKEN, None)
                self._pending_data = None
                return self.async_create_entry(title="GitHub Copilot", data=data)
        if self._reasoning_metadata_error and "base" not in errors:
            errors["base"] = self._reasoning_metadata_error
        return self.async_show_form(
            step_id="reasoning",
            data_schema=_reasoning_schema(self._reasoning_capabilities, selected),
            errors=errors,
            description_placeholders={
                "model": data[CONF_MODEL],
                "default_effort": self._reasoning_capabilities.default_effort or "-",
            },
            last_step=True,
        )

    async def _test_credentials(
        self,
        api_token: str,
        model: str,
        cli_url: str = DEFAULT_CLI_URL,
        mcp_config: str = DEFAULT_MCP_CONFIG,
        reasoning_effort: str | None = None,
    ) -> None:
        """Validate credentials."""
        client = _client_for_config(
            {
                CONF_API_TOKEN: api_token,
                CONF_MODEL: model,
                CONF_CLI_URL: cli_url,
                CONF_MCP_CONFIG: mcp_config,
            },
            reasoning_effort=reasoning_effort,
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

    _pending_data: dict[str, Any] | None = None
    _reasoning_capabilities = ReasoningCapabilities()
    _reasoning_metadata_error: str | None = None

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle options flow."""
        _errors: dict[str, str] = {}
        if user_input is not None:
            cli_url = user_input.get(CONF_CLI_URL, DEFAULT_CLI_URL).strip()
            mcp_config = user_input.get(CONF_MCP_CONFIG, DEFAULT_MCP_CONFIG) or ""

            # Apply the same http/https validation as the initial config flow
            if cli_url and not _validate_cli_url(cli_url):
                _errors[CONF_CLI_URL] = "invalid_url"

            # Validate MCP config if provided
            if mcp_config and not await _async_validate_mcp_config(mcp_config):
                _errors[CONF_MCP_CONFIG] = "invalid_mcp"

            if not _errors:
                self._pending_data = {
                    **self.config_entry.data,
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_CLI_URL: cli_url,
                    CONF_TIMEOUT: float(user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
                    CONF_MCP_CONFIG: mcp_config,
                }
                result = await self.async_step_reasoning()
                if self._reasoning_metadata_error != "auth":
                    return result
                self._pending_data = None
                _errors["base"] = "auth"

        # Get current model from config entry, normalizing any legacy IDs.
        current_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        current_model = LEGACY_MODEL_MAP.get(current_model, current_model)

        # Get current CLI URL from config entry
        current_cli_url = self.config_entry.data.get(CONF_CLI_URL, DEFAULT_CLI_URL)

        # Get current MCP config from config entry
        current_mcp_config = self.config_entry.data.get(
            CONF_MCP_CONFIG, DEFAULT_MCP_CONFIG
        )

        # Get current timeout from config entry
        current_timeout = float(
            self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        )

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
                    vol.Optional(
                        CONF_MCP_CONFIG,
                        default=current_mcp_config,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=current_timeout,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=600,
                            step=10,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            ),
            errors=_errors,
            last_step=False,
        )

    async def async_step_reasoning(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Validate the model/effort pair before saving any options changes."""
        if self._pending_data is None:
            return await self.async_step_init()
        data = self._pending_data
        if user_input is None or not self._reasoning_capabilities.known:
            (
                self._reasoning_capabilities,
                self._reasoning_metadata_error,
            ) = await _async_reasoning_metadata(data)
        selected = (
            user_input[CONF_REASONING_EFFORT]
            if user_input is not None
            else data.get(CONF_REASONING_EFFORT) or DEFAULT_REASONING_EFFORT
        )
        errors = _reasoning_errors(self._reasoning_capabilities, selected)
        if user_input is not None and not errors:
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=_with_reasoning_choice(data, selected)
            )
            self._pending_data = None
            return self.async_create_entry(title="", data={})
        if self._reasoning_metadata_error:
            errors["base"] = self._reasoning_metadata_error
        return self.async_show_form(
            step_id="reasoning",
            data_schema=_reasoning_schema(self._reasoning_capabilities, selected),
            errors=errors,
            description_placeholders={
                "model": data[CONF_MODEL],
                "default_effort": self._reasoning_capabilities.default_effort or "-",
            },
            last_step=True,
        )
