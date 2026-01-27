"""GitHub Copilot API Client."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout


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


async def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = f"Authentication failed (HTTP {response.status}): Invalid API token"
        raise GitHubCopilotApiClientAuthenticationError(msg)
    if response.status == 404:  # noqa: PLR2004
        msg = f"API endpoint not found (HTTP {response.status})"
        raise GitHubCopilotApiClientCommunicationError(msg)
    if response.status == 400:  # noqa: PLR2004
        # Try to get more details from the response body for Bad Request errors
        try:
            error_body = await response.json()
            error_detail = error_body.get("error", {}).get("message", "Bad Request")
        except Exception:  # noqa: BLE001
            error_detail = "Bad Request - invalid request format or parameters"
        msg = f"API request failed (HTTP 400): {error_detail}"
        raise GitHubCopilotApiClientError(msg)
    if response.status >= 400:  # noqa: PLR2004
        msg = f"API request failed with HTTP {response.status}"
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
        return await self._api_wrapper(
            method="post",
            url=self._base_url,
            data={
                "messages": messages,
                "model": self._model,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
            },
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
