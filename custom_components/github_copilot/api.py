"""GitHub Copilot SDK Client wrapper."""

from __future__ import annotations

import asyncio
import os
import shutil
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
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
class CopilotDiagnostics:
    """Diagnostics information for troubleshooting connection issues."""

    cli_installed: bool = False
    cli_path: str | None = None
    auth_status: str = "unknown"
    error_details: str = ""
    suggestions: list[str] = field(default_factory=list)

    def to_user_message(self) -> str:
        """Generate user-friendly diagnostic message."""
        parts = []
        if not self.cli_installed:
            parts.append("GitHub Copilot CLI is not installed or not found in PATH.")
            parts.append("Please install it from: https://docs.github.com/copilot/cli")
        elif self.auth_status == "not_authenticated":
            parts.append("GitHub Copilot CLI is installed but not authenticated.")
            parts.append("Please run 'copilot auth login' to authenticate.")
        elif self.error_details:
            parts.append(f"Error: {self.error_details}")

        if self.suggestions:
            parts.append("Suggestions:")
            parts.extend(f"  - {suggestion}" for suggestion in self.suggestions)

        return " ".join(parts) if parts else "Unknown error"


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
            except TimeoutError as exception:
                LOGGER.error(
                    "Timeout creating Copilot session with model '%s': %s",
                    self._model,
                    exception,
                )
                msg = (
                    f"Timeout creating session with model '{self._model}'. "
                    "The Copilot service may be slow or unavailable."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from exception
            except ValueError as exception:
                LOGGER.error(
                    "Invalid configuration for Copilot session: %s",
                    exception,
                )
                msg = (
                    f"Invalid session configuration for model '{self._model}': "
                    f"{exception}"
                )
                raise GitHubCopilotApiClientError(msg) from exception
            except Exception as exception:
                LOGGER.error(
                    "Failed to create Copilot session with model '%s': %s - %s",
                    self._model,
                    type(exception).__name__,
                    str(exception),
                )
                msg = (
                    f"Unable to start Copilot session with model '{self._model}': "
                    f"{type(exception).__name__}. Check the logs for details."
                )
                raise GitHubCopilotApiClientError(msg) from exception
            session_context = CopilotSessionContext(
                session_id=copilot_session.session_id,
                copilot_session=copilot_session,
            )
            self._sessions[session_context.session_id] = session_context
            LOGGER.debug(
                "Created Copilot session %s with model '%s'",
                session_context.session_id,
                self._model,
            )
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
            msg = "Prompt cannot be empty. Please provide a message."
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)

        async with self._session_lock:
            session = self._sessions.get(session_id)
        if not session:
            msg = f"Session '{session_id}' not found. The session may have expired."
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)

        try:
            event = await session.copilot_session.send_and_wait({"prompt": prompt})
        except TimeoutError as exception:
            LOGGER.error(
                "Copilot session %s timed out waiting for response: %s",
                session_id,
                exception,
            )
            msg = (
                "Request timed out waiting for Copilot response. "
                "Please try again or check your connection."
            )
            raise GitHubCopilotApiClientCommunicationError(msg) from exception
        except ConnectionError as exception:
            LOGGER.error(
                "Connection error in Copilot session %s: %s",
                session_id,
                exception,
            )
            msg = "Lost connection to Copilot. Please check your network and try again."
            raise GitHubCopilotApiClientCommunicationError(msg) from exception
        except Exception as exception:
            LOGGER.error(
                "Copilot session %s error: %s - %s",
                session_id,
                type(exception).__name__,
                str(exception),
            )
            msg = (
                f"Copilot failed to respond: {type(exception).__name__}. "
                "Please check the logs for details."
            )
            raise GitHubCopilotApiClientError(msg) from exception

        if event is None:
            msg = (
                "No response received from Copilot. "
                "The service may be experiencing issues."
            )
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg)

        content = getattr(event.data, "content", None)
        if not content:
            msg = (
                "Copilot returned an empty response. "
                "Please try rephrasing your request."
            )
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

    def _check_cli_installed(self) -> CopilotDiagnostics:
        """Check if GitHub Copilot CLI is installed and accessible."""
        diagnostics = CopilotDiagnostics()

        # Check for copilot CLI in PATH
        cli_path = shutil.which("copilot")
        if cli_path:
            diagnostics.cli_installed = True
            diagnostics.cli_path = cli_path
        else:
            # Also check common installation locations
            common_paths = [
                Path.home() / ".local" / "bin" / "copilot",
                Path("/usr/local/bin/copilot"),
                Path("/usr/bin/copilot"),
            ]
            for path in common_paths:
                if path.is_file() and os.access(path, os.X_OK):
                    diagnostics.cli_installed = True
                    diagnostics.cli_path = str(path)
                    break

        if not diagnostics.cli_installed:
            diagnostics.suggestions = [
                "Install the GitHub Copilot CLI: https://docs.github.com/copilot/cli",
                "Ensure the CLI is in your PATH",
                "Check if you have an active GitHub Copilot subscription",
            ]

        return diagnostics

    async def _ensure_client(self) -> copilot.CopilotClient:
        """Ensure the Copilot SDK client is started."""
        async with self._client_lock:
            if self._client:
                return self._client

            # First check if CLI is installed
            diagnostics = self._check_cli_installed()
            if not diagnostics.cli_installed:
                LOGGER.error(
                    "GitHub Copilot CLI not found. %s",
                    diagnostics.to_user_message(),
                )
                msg = (
                    "GitHub Copilot CLI not found. "
                    "Please install it from https://docs.github.com/copilot/cli "
                    "and ensure it's in your PATH."
                )
                raise GitHubCopilotApiClientCommunicationError(msg)

            client = copilot.CopilotClient(self._client_options)
            try:
                await client.start()
            except FileNotFoundError as exception:
                LOGGER.error(
                    "Copilot CLI executable not found: %s",
                    exception,
                )
                msg = (
                    "GitHub Copilot CLI executable not found. "
                    "Please install it from https://docs.github.com/copilot/cli"
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from exception
            except PermissionError as exception:
                LOGGER.error(
                    "Permission denied when starting Copilot CLI: %s",
                    exception,
                )
                msg = (
                    "Permission denied when starting GitHub Copilot CLI. "
                    "Please check file permissions."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from exception
            except ConnectionRefusedError as exception:
                LOGGER.error(
                    "Connection refused by Copilot CLI: %s",
                    exception,
                )
                msg = (
                    "Connection refused by GitHub Copilot CLI. "
                    "The CLI server may not be running or is misconfigured."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from exception
            except OSError as exception:
                LOGGER.error(
                    "OS error when starting Copilot CLI: %s - %s",
                    type(exception).__name__,
                    exception,
                )
                msg = (
                    f"Failed to start GitHub Copilot CLI: {exception}. "
                    "Please verify the CLI is properly installed."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from exception
            except Exception as exception:
                LOGGER.error(
                    "Failed to start Copilot SDK client: %s - %s",
                    type(exception).__name__,
                    str(exception),
                )
                exc_name = type(exception).__name__
                msg = (
                    f"Unable to connect to GitHub Copilot CLI: {exc_name}. "
                    "Please check the logs for more details."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from exception

            try:
                auth_status = await client.get_auth_status()
            except Exception as exception:
                LOGGER.error(
                    "Failed to get Copilot authentication status: %s - %s",
                    type(exception).__name__,
                    str(exception),
                )
                msg = (
                    "Failed to verify Copilot CLI authentication. "
                    "Please run 'copilot auth login' to authenticate."
                )
                raise GitHubCopilotApiClientAuthenticationError(msg) from exception

            if not auth_status.isAuthenticated:
                LOGGER.warning(
                    "Copilot CLI is not authenticated. "
                    "User needs to run 'copilot auth login'"
                )
                msg = (
                    "GitHub Copilot CLI is not authenticated. "
                    "Please run 'copilot auth login' to authenticate, "
                    "or provide a valid GitHub token with Copilot access."
                )
                raise GitHubCopilotApiClientAuthenticationError(msg)

            LOGGER.info("Successfully connected to GitHub Copilot CLI")
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
