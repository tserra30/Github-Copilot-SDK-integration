"""GitHub Copilot SDK Client wrapper."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import copilot

from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Sequence


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


@dataclass
class CopilotSessionContext:
    """In-memory session context for Copilot SDK conversations."""

    session_id: str
    copilot_session: copilot.CopilotSession


class GitHubCopilotApiClient:
    """GitHub Copilot SDK client wrapper."""

    def __init__(
        self,
        model: str = "gpt-4o",
        *,
        client_options: dict[str, Any] | None = None,
    ) -> None:
        """Initialize GitHub Copilot SDK client wrapper."""
        self._model = model
        self._client_options = client_options or {}
        self._client: copilot.CopilotClient | None = None
        self._sessions: dict[str, CopilotSessionContext] = {}
        self._session_lock = asyncio.Lock()
        self._client_lock = asyncio.Lock()

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
        session = await self.async_create_session()
        try:
            await self.async_send_prompt(session.session_id, "Hello")
        finally:
            await self.async_end_session(session.session_id)
        return True

    async def async_create_session(self) -> CopilotSessionContext:
        """Create a Copilot SDK session."""
        async with self._session_lock:
            client = await self._ensure_client()
            try:
                copilot_session = await client.create_session(
                    {
                        "model": self._model,
                        "streaming": False,
                    }
                )
            except Exception as exception:
                LOGGER.error(
                    "Failed to create Copilot session: %s",
                    type(exception).__name__,
                )
                msg = "Unable to start Copilot session."
                raise GitHubCopilotApiClientError(msg) from exception
            session_context = CopilotSessionContext(
                session_id=copilot_session.session_id,
                copilot_session=copilot_session,
            )
            self._sessions[session_context.session_id] = session_context
            return session_context

    async def async_end_session(self, session_id: str) -> None:
        """Destroy a Copilot SDK session."""
        async with self._session_lock:
            session = self._sessions.pop(session_id, None)
        if not session:
            return
        try:
            await session.copilot_session.destroy()
        except Exception as exception:
            LOGGER.error(
                "Failed to destroy Copilot session: %s",
                type(exception).__name__,
            )
            msg = "Unable to clean up Copilot session."
            raise GitHubCopilotApiClientError(msg) from exception

    async def async_send_prompt(self, session_id: str, prompt: str) -> str:
        """Send a prompt to an existing Copilot SDK session."""
        if not prompt.strip():
            msg = "Prompt cannot be empty"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)

        async with self._session_lock:
            session = self._sessions.get(session_id)
        if not session:
            msg = "Session not found"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)

        try:
            event = await session.copilot_session.send_and_wait({"prompt": prompt})
        except TimeoutError as exception:
            LOGGER.error("Copilot session timed out waiting for response")
            msg = "Copilot session timed out."
            raise GitHubCopilotApiClientCommunicationError(msg) from exception
        except Exception as exception:
            LOGGER.error(
                "Copilot session error: %s",
                type(exception).__name__,
            )
            msg = "Copilot session failed to respond."
            raise GitHubCopilotApiClientError(msg) from exception

        if event is None:
            msg = "No response received from Copilot session"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)

        content = getattr(event.data, "content", None)
        if not content:
            msg = "Copilot session returned empty content"
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)
        return content

    async def async_close(self) -> None:
        """Close the Copilot SDK client and sessions."""
        async with self._session_lock:
            session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            with suppress(GitHubCopilotApiClientError):
                await self.async_end_session(session_id)
        async with self._client_lock:
            if self._client:
                await self._client.stop()
                self._client = None

    async def _ensure_client(self) -> copilot.CopilotClient:
        """Ensure the Copilot SDK client is started."""
        async with self._client_lock:
            if self._client:
                return self._client
            client = copilot.CopilotClient(self._client_options)
            try:
                await client.start()
                auth_status = await client.get_auth_status()
            except Exception as exception:
                LOGGER.error(
                    "Failed to start Copilot SDK client: %s",
                    type(exception).__name__,
                )
                msg = "Unable to connect to Copilot CLI."
                raise GitHubCopilotApiClientCommunicationError(msg) from exception
            if not auth_status.isAuthenticated:
                msg = "Copilot CLI authentication failed."
                raise GitHubCopilotApiClientAuthenticationError(msg)
            self._client = client
            return client

    async def async_available_models(self) -> Sequence[str]:
        """Return available model IDs from the Copilot SDK."""
        client = await self._ensure_client()
        try:
            models = await client.list_models()
        except Exception as exception:
            LOGGER.error(
                "Failed to list Copilot models: %s",
                type(exception).__name__,
            )
            msg = "Unable to fetch Copilot models."
            raise GitHubCopilotApiClientCommunicationError(msg) from exception
        return [model.id for model in models]
