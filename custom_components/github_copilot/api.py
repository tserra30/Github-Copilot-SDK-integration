"""GitHub Copilot API Client."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout

from .const import CLAUDE_MODELS, LOGGER, REASONING_MODELS


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
        error_body = await response.json()
        LOGGER.debug("API error response body: %s", error_body)
        error_detail = error_body.get("error", {}).get("message", "Unknown error")
        error_code = error_body.get("error", {}).get("code", "")
    except Exception:  # noqa: BLE001
        LOGGER.debug("Could not parse error response body")
        return "Unknown error", ""
    else:
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
        if error_code:
            error_detail = f"{error_detail} (code: {error_code})"
        msg = f"API request failed (HTTP {response.status}): {error_detail}"
        raise GitHubCopilotApiClientError(msg)
    response.raise_for_status()


class GitHubCopilotApiClient:
    """GitHub Copilot API Client."""

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
        self._base_url = "https://api.githubcopilot.com/chat/completions"

    async def async_chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Send chat messages to GitHub Copilot API."""
        # Validate messages
        if not messages:
            msg = "Messages list cannot be empty"
            raise GitHubCopilotApiClientError(msg)

        # Validate each message has required fields
        for i, message in enumerate(messages):
            if "role" not in message:
                msg = f"Message at index {i} missing 'role' field"
                raise GitHubCopilotApiClientError(msg)
            if "content" not in message:
                msg = f"Message at index {i} missing 'content' field"
                raise GitHubCopilotApiClientError(msg)
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                msg = (
                    f"Message at index {i} has invalid 'content'; "
                    "expected a non-empty string"
                )
                raise GitHubCopilotApiClientError(msg)
            if message["role"] not in ("user", "assistant", "system"):
                msg = f"Invalid role '{message['role']}' at index {i}"
                raise GitHubCopilotApiClientError(msg)

        # Build request data based on model type
        data: dict[str, Any] = {
            "messages": messages,
            "model": self._model,
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
                    "clamping to %.3f (valid range is 0.0–1.0)",
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

        headers.update(
            {
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            }
        )

        try:
            async with async_timeout.timeout(30):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                await _verify_response_or_raise(response)
                return await response.json()

        except GitHubCopilotApiClientError:
            # Re-raise our own exceptions without wrapping them
            raise
        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise GitHubCopilotApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise GitHubCopilotApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise GitHubCopilotApiClientError(
                msg,
            ) from exception
