"""GitHub Copilot API Client."""

from __future__ import annotations

import json
import socket
import time
import uuid
from typing import Any

import aiohttp
import async_timeout

from .const import (
    API_TIMEOUT,
    CLAUDE_MODELS,
    COPILOT_INTEGRATION_ID,
    EDITOR_PLUGIN_VERSION,
    EDITOR_VERSION,
    LOGGER,
    REASONING_MODELS,
    USER_AGENT,
)


class GitHubCopilotApiClientError(Exception):
    """Exception to indicate a general API error."""


class GitHubCopilotApiClientCommunicationError(
    GitHubCopilotApiClientError,
):
    """Exception to indicate a communication error."""


class GitHubCopilotApiClientAuthenticationError(
    GitHubCopilotApiClientError,
):
    """Exception to indicate an authentication error."""


async def _get_error_detail(response: aiohttp.ClientResponse) -> tuple[str, str]:
    """Extract error details from API response."""
    try:
        # Use content_type=None to allow parsing responses with
        # non-standard content types
        error_body = await response.json(content_type=None)
        LOGGER.debug("API error response body: %s", error_body)
        error_detail = error_body.get("error", {}).get("message", "Unknown error")
        error_code = error_body.get("error", {}).get("code", "")
    except (
        json.JSONDecodeError,
        ValueError,
        KeyError,
        TypeError,
        aiohttp.ContentTypeError,
    ) as err:
        LOGGER.debug("Could not parse error response body: %s", err)
        return "Unknown error", ""
    return error_detail, error_code


async def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = f"Authentication failed (HTTP {response.status}): Invalid API token"
        raise GitHubCopilotApiClientAuthenticationError(msg)
    if response.status == 404:  # noqa: PLR2004
        msg = f"API endpoint not found (HTTP {response.status})"
        raise GitHubCopilotApiClientCommunicationError(msg)
    if response.status == 400:  # noqa: PLR2004
        error_detail, error_code = await _get_error_detail(response)
        if error_detail == "Unknown error":
            error_detail = "Bad Request - invalid request format or parameters"
        if error_code:
            error_detail = f"{error_detail} (code: {error_code})"
        msg = f"API request failed (HTTP 400): {error_detail}"
        raise GitHubCopilotApiClientError(msg)
    if response.status >= 400:  # noqa: PLR2004
        error_detail, error_code = await _get_error_detail(response)
        if error_detail == "Unknown error":
            error_detail = "HTTP error - unable to parse response details"
        if error_code:
            error_detail = f"{error_detail} (code: {error_code})"
        msg = f"API request failed (HTTP {response.status}): {error_detail}"
        raise GitHubCopilotApiClientError(msg)
    response.raise_for_status()


class GitHubCopilotApiClient:
    """GitHub Copilot API Client."""

    # URL to exchange GitHub PAT for Copilot token
    _COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"  # noqa: S105
    # Chat completions URL
    _CHAT_URL = "https://api.githubcopilot.com/chat/completions"
    # Copilot token cache duration in seconds (tokens valid for ~2 hours)
    _TOKEN_CACHE_DURATION = 2 * 60 * 60  # 2 hours

    def __init__(
        self,
        api_token: str,
        session: aiohttp.ClientSession,
        model: str = "gpt-4o",
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> None:
        """Initialize GitHub Copilot API Client."""
        self._api_token = api_token
        self._session = session
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._base_url = self._CHAT_URL
        # Generate machine ID and session ID for GitHub Copilot API
        self._machine_id = str(uuid.uuid4())
        self._session_id = f"{uuid.uuid4()}{int(time.time() * 1000)}"
        # Cached Copilot token and its expiration time
        self._copilot_token: str | None = None
        self._copilot_token_expires: float = 0

    async def _get_copilot_token(self) -> str:
        """
        Exchange GitHub PAT for a Copilot API token.

        GitHub Copilot requires a two-step authentication process:
        1. Use GitHub PAT to request a Copilot-specific token
        2. Use that Copilot token for chat API requests

        Returns:
            str: The Copilot API token.

        Raises:
            GitHubCopilotApiClientAuthenticationError: If authentication fails.
            GitHubCopilotApiClientCommunicationError: If connection fails.
            GitHubCopilotApiClientError: For other API errors.

        """
        # Return cached token if still valid
        if self._copilot_token and time.time() < self._copilot_token_expires:
            LOGGER.debug("Using cached Copilot token")
            return self._copilot_token

        LOGGER.debug("Requesting new Copilot token")

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

        try:
            async with async_timeout.timeout(API_TIMEOUT):
                response = await self._session.get(
                    url=self._COPILOT_TOKEN_URL,
                    headers=headers,
                )

                if response.status in (401, 403):
                    msg = (
                        f"Authentication failed (HTTP {response.status}): "
                        "Invalid GitHub token or no Copilot access"
                    )
                    raise GitHubCopilotApiClientAuthenticationError(msg)

                if response.status != 200:  # noqa: PLR2004
                    error_detail, _ = await _get_error_detail(response)
                    msg = (
                        f"Failed to get Copilot token (HTTP {response.status}): "
                        f"{error_detail}"
                    )
                    raise GitHubCopilotApiClientError(msg)  # noqa: TRY301

                data = await response.json(content_type=None)
                token = data.get("token")

                if not token:
                    msg = "No token in Copilot token response"
                    raise GitHubCopilotApiClientError(msg)  # noqa: TRY301

                # Cache the token with expiration
                self._copilot_token = token
                self._copilot_token_expires = time.time() + self._TOKEN_CACHE_DURATION
                LOGGER.debug("Successfully obtained Copilot token")
                return token

        except GitHubCopilotApiClientError:
            raise
        except TimeoutError as exception:
            msg = "Timeout while requesting Copilot token"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = (
                f"Connection error while requesting Copilot token: "
                f"{type(exception).__name__}"
            )
            LOGGER.error(msg)
            raise GitHubCopilotApiClientCommunicationError(msg) from exception

    async def async_chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Send chat messages to GitHub Copilot API."""
        # Validate messages
        if not messages:
            msg = "Messages list cannot be empty"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)

        # Validate each message has required fields
        for i, message in enumerate(messages):
            if "role" not in message:
                msg = f"Message at index {i} missing 'role' field"
                LOGGER.error(msg)
                raise GitHubCopilotApiClientError(msg)
            if "content" not in message:
                msg = f"Message at index {i} missing 'content' field"
                LOGGER.error(msg)
                raise GitHubCopilotApiClientError(msg)

            role = message["role"]
            content = message["content"]

            if not isinstance(role, str):
                msg = (
                    f"Message at index {i} has non-string 'role' field: "
                    f"{type(role).__name__}"
                )
                LOGGER.error(msg)
                raise GitHubCopilotApiClientError(msg)

            if not isinstance(content, str):
                msg = (
                    f"Message at index {i} has non-string 'content' field: "
                    f"{type(content).__name__}"
                )
                LOGGER.error(msg)
                raise GitHubCopilotApiClientError(msg)

            if not content.strip():
                msg = (
                    f"Message at index {i} has invalid 'content'; "
                    "expected a non-empty string"
                )
                LOGGER.error(msg)
                raise GitHubCopilotApiClientError(msg)

            if role not in ("user", "assistant", "system"):
                msg = f"Invalid role '{role}' at index {i}"
                LOGGER.error(msg)
                raise GitHubCopilotApiClientError(msg)

        # Build request data based on model type
        data: dict[str, Any] = {
            "messages": messages,
            "model": self._model,
            "stream": False,  # Required by GitHub Copilot API
        }

        # Reasoning models (o1, o1-mini, o3-mini) don't support temperature
        # and use max_completion_tokens instead of max_tokens
        if self._model in REASONING_MODELS:
            data["max_completion_tokens"] = self._max_tokens
        # Claude models use standard parameters but temperature is clamped to 0-1
        elif self._model in CLAUDE_MODELS:
            data["max_tokens"] = self._max_tokens
            # Clamp temperature to Claude's valid range (0.0-1.0)
            clamped_temp = max(0.0, min(1.0, self._temperature))
            if clamped_temp != self._temperature:
                LOGGER.info(
                    "Temperature %.3f is out of range for Claude models; "
                    "clamping to %.3f (valid range is 0.0-1.0)",
                    self._temperature,
                    clamped_temp,
                )
            data["temperature"] = clamped_temp
        else:
            # Standard OpenAI models
            data["max_tokens"] = self._max_tokens
            data["temperature"] = self._temperature

        return await self._api_wrapper(
            method="post",
            url=self._base_url,
            data=data,
        )

    async def async_test_connection(self) -> bool:
        """
        Test the API connection.

        Raises:
            GitHubCopilotApiClientAuthenticationError: If authentication fails.
            GitHubCopilotApiClientCommunicationError: If connection fails.
            GitHubCopilotApiClientError: For other API errors.

        Returns:
            True if connection is successful.

        """
        await self.async_chat([{"role": "user", "content": "Hello"}])
        return True

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        if headers is None:
            headers = {}

        # Get the Copilot token (exchanges PAT for Copilot-specific token)
        copilot_token = await self._get_copilot_token()

        # Add required headers for GitHub Copilot API
        headers.update(
            {
                "Authorization": f"Bearer {copilot_token}",
                "Content-Type": "application/json",
                "x-request-id": str(uuid.uuid4()),
                "vscode-machineid": self._machine_id,
                "vscode-sessionid": self._session_id,
                "openai-organization": "github-copilot",
                "openai-intent": "conversation-panel",
                "Copilot-Integration-Id": COPILOT_INTEGRATION_ID,
                "editor-version": EDITOR_VERSION,
                "editor-plugin-version": EDITOR_PLUGIN_VERSION,
                "user-agent": USER_AGENT,
            }
        )

        try:
            LOGGER.debug("Making %s request to %s", method.upper(), url)
            async with async_timeout.timeout(API_TIMEOUT):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                LOGGER.debug("Received response with status %s", response.status)
                await _verify_response_or_raise(response)
                # Use content_type=None to handle responses with unexpected
                # content types gracefully instead of raising ContentTypeError
                return await response.json(content_type=None)

        except GitHubCopilotApiClientError:
            # Re-raise our own exceptions without wrapping them
            raise
        except TimeoutError as exception:
            # Don't include exception details to avoid exposing sensitive data
            # such as API tokens, request URLs, or response data
            msg = "Timeout error fetching information"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientCommunicationError(
                msg,
            ) from exception
        except aiohttp.ContentTypeError as exception:
            # This handler is kept for defensive purposes in case future changes
            # introduce paths that could raise ContentTypeError, or if aiohttp
            # behavior changes. Currently, content_type=None prevents this.
            msg = "API returned non-JSON response - check API endpoint and credentials"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientCommunicationError(
                msg,
            ) from exception
        except json.JSONDecodeError as exception:
            # Handle invalid JSON in response body
            msg = (
                "API returned invalid JSON response - "
                "check API endpoint and credentials"
            )
            LOGGER.error(msg)
            raise GitHubCopilotApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            # Don't include exception details in the message to avoid
            # leaking sensitive data such as API tokens that might be
            # in headers or URLs
            msg = f"Error fetching information - {type(exception).__name__}"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            # Don't include exception details to avoid leaking sensitive information
            msg = f"Unexpected error occurred - {type(exception).__name__}"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(
                msg,
            ) from exception
