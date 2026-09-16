"""GitHub Copilot SDK Client wrapper."""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
from contextlib import suppress
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    import copilot as copilot  # noqa: PLC0414 — only for type annotations
    from copilot.session import PermissionInvocation, PermissionRequest

try:
    import copilot  # type: ignore[no-redef]

    _COPILOT_SDK_AVAILABLE = True
except ImportError:
    _COPILOT_SDK_AVAILABLE = False

from .const import DEFAULT_MODEL, LOGGER
from .mcp import async_load_mcp_config

_SDK_INSTALL_HINT = (
    "The github-copilot-sdk package is required but is not installed. "
    "Install it with: pip install 'github-copilot-sdk==1.0.13'. "
    "The official universal wheel supports Home Assistant OS."
)

# Each detach/delete operation gets its own timeout, including normal cleanup.
_SESSION_DESTROY_TIMEOUT = 5.0


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
class CliInstallationStatus:
    """
    Status information for Copilot CLI installation check.

    This dataclass collects information about CLI installation status,
    helping users understand if the CLI is properly installed and accessible.

    Attributes:
        cli_installed: Whether the Copilot CLI was found on the system.
        cli_path: Path to the Copilot CLI executable, if found.
        error_details: Specific error message for troubleshooting.
        suggestions: List of suggestions for the user to try.

    """

    cli_installed: bool = False
    cli_path: str | None = None
    error_details: str = ""
    suggestions: list[str] = field(default_factory=list)

    def to_user_message(self) -> str:
        """Generate user-friendly diagnostic message."""
        parts = []
        if not self.cli_installed:
            parts.append("GitHub Copilot CLI is not installed or not found in PATH.")
            parts.append("Please install it from: https://docs.github.com/copilot/cli")
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
        model: str = DEFAULT_MODEL,
        *,
        client_options: dict[str, Any] | None = None,
        timeout: float = 120.0,
        mcp_config: str = "",
    ) -> None:
        """Initialize GitHub Copilot SDK client wrapper."""
        self._model = model
        self._client_options = client_options or {}
        self._timeout = timeout
        self._mcp_config = mcp_config
        self._mcp_servers: dict[str, copilot.MCPServerConfig] = {}
        self._mcp_servers_loaded = False
        self._client: copilot.CopilotClient | None = None
        self._sessions: dict[str, CopilotSessionContext] = {}
        self._session_lock = asyncio.Lock()
        self._client_lock = asyncio.Lock()

    @property
    def has_mcp_tools(self) -> bool:
        """Return whether the loaded configuration authorizes any MCP tools."""
        return any(server["tools"] for server in self._mcp_servers.values())

    async def async_load_mcp_servers(self) -> None:
        """Load shared MCP configuration once per integration instance."""
        if self._mcp_servers_loaded:
            return
        try:
            self._mcp_servers = await async_load_mcp_config(self._mcp_config)
        except ValueError as exception:
            msg = (
                "Invalid MCP configuration. Provide valid mcpServers JSON or a "
                "readable JSON file inside Home Assistant, not only the bridge. "
                "Every server requires an explicit tools list."
            )
            LOGGER.error(msg)
            raise GitHubCopilotApiClientError(msg) from exception
        self._mcp_servers_loaded = True

    def _handle_permission_request(
        self,
        request: PermissionRequest,
        invocation: PermissionInvocation,
    ) -> copilot.PermissionRequestResult:
        """Approve only explicitly configured MCP tools, never CLI host access."""
        from copilot.rpc import (  # noqa: PLC0415
            PermissionDecisionApproveOnce,
            PermissionDecisionUserNotAvailable,
        )
        from copilot.session_events import PermissionRequestMcp  # noqa: PLC0415

        if (
            not invocation.get("managed_settings_enabled", False)
            and not getattr(request, "managed_approval_required", False)
            and isinstance(request, PermissionRequestMcp)
        ):
            server = self._mcp_servers.get(request.server_name)
            if server is not None:
                tools = server.get("tools", [])
                # CLI permission IDs are server-qualified; MCP allowlists are not.
                prefix = f"{request.server_name}-"
                if request.tool_name.startswith(prefix):
                    tool_name = request.tool_name[len(prefix) :]
                    if tool_name and ("*" in tools or tool_name in tools):
                        return PermissionDecisionApproveOnce()
        LOGGER.warning(
            "Denied a Copilot tool permission outside configured MCP access."
        )
        return PermissionDecisionUserNotAvailable()

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
        session = None
        try:
            session = await self.async_create_session()
            await self.async_send_prompt(session.session_id, "Hello")
        finally:
            if session:
                await self.async_end_session(session.session_id)
        LOGGER.info("Copilot connection test succeeded: model response received.")
        return True

    async def async_create_session(self) -> CopilotSessionContext:
        """Create a Copilot SDK session."""
        async with self._session_lock:
            client = await self._ensure_client()
            try:
                copilot_session = await client.create_session(
                    model=self._model,
                    streaming=False,
                    mcp_servers=self._mcp_servers,
                    on_permission_request=self._handle_permission_request,
                    available_tools=copilot.ToolSet().add_mcp("*"),
                    disabled_mcp_servers=["github-mcp-server"],
                    system_message={
                        "mode": "replace",
                        "content": (
                            "You are a Home Assistant conversation assistant. "
                            "Use the configured MCP tools for current home state "
                            "and device actions. Never claim an action succeeded "
                            "unless its tool result confirms it. If a tool is "
                            "unavailable or denied, explain that clearly."
                        ),
                    },
                )
            except TimeoutError as exception:
                LOGGER.error(
                    "Timeout creating Copilot session (%s).",
                    type(exception).__name__,
                )
                msg = (
                    f"Timeout creating session with model '{self._model}'. "
                    "The Copilot service may be slow or unavailable."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from None
            except ValueError as exception:
                LOGGER.error(
                    "Invalid configuration for Copilot session (%s).",
                    type(exception).__name__,
                )
                msg = (
                    "Invalid Copilot session configuration. "
                    "Check the selected model and MCP settings."
                )
                raise GitHubCopilotApiClientError(msg) from None
            except Exception as exception:  # noqa: BLE001 - SDK error boundary.
                LOGGER.error(
                    "Failed to create Copilot session (%s).",
                    type(exception).__name__,
                )
                msg = (
                    "Unable to start a Copilot session. Check the bridge logs "
                    "and choose an available model through Configure."
                )
                raise GitHubCopilotApiClientError(msg) from None
            session_context = CopilotSessionContext(
                session_id=copilot_session.session_id,
                copilot_session=copilot_session,
            )
            self._sessions[session_context.session_id] = session_context
            LOGGER.info(
                "Copilot session started "
                "(requested model=%s, configured MCP servers=%d).",
                self._model,
                len(self._mcp_servers),
            )
            return session_context

    async def async_end_session(self, session_id: str) -> None:
        """Destroy a Copilot SDK session."""
        async with self._session_lock:
            session = self._sessions.pop(session_id, None)
        if not session:
            return
        if not await self._cleanup_session(session):
            msg = "Unable to clean up Copilot session."
            raise GitHubCopilotApiClientError(msg) from None
        LOGGER.info("Copilot session closed.")

    async def _cleanup_session(
        self, session: CopilotSessionContext, *, best_effort: bool = False
    ) -> bool:
        """Attempt detach and persisted-state deletion independently."""
        operations: list[tuple[str, Callable[[], Awaitable[None]]]] = [
            ("disconnect", session.copilot_session.disconnect),
        ]
        if self._client:
            operations.append(
                ("delete", partial(self._client.delete_session, session.session_id))
            )
        succeeded = True
        log_failure = LOGGER.warning if best_effort else LOGGER.error
        for operation, cleanup in operations:
            try:
                await asyncio.wait_for(cleanup(), timeout=_SESSION_DESTROY_TIMEOUT)
            except Exception as exception:  # noqa: BLE001 - SDK error boundary.
                succeeded = False
                log_failure(
                    "Failed to close Copilot session during %s (%s).",
                    operation,
                    type(exception).__name__,
                )
        return succeeded

    async def _evict_broken_session(self, session_id: str) -> None:
        """
        Remove a broken session from the registry and attempt best-effort cleanup.

        Called after a communication failure when the underlying SDK session
        may be in an indeterminate state. The session is popped under the lock
        to prevent reuse, then detach and delete are attempted independently
        outside the lock, each with a short timeout. Failures are logged without
        replacing the original communication error.
        """
        async with self._session_lock:
            session = self._sessions.pop(session_id, None)

        if session is None:
            return

        await self._cleanup_session(session, best_effort=True)

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

        LOGGER.debug("Sending Copilot request (timeout=%.0fs).", self._timeout)
        try:
            event = await session.copilot_session.send_and_wait(
                prompt, timeout=self._timeout
            )
        except TimeoutError:
            LOGGER.error(
                "Copilot request timed out after %.0fs.",
                self._timeout,
            )
            # Remove the stale session so it cannot be reused in a broken state.
            await self._evict_broken_session(session_id)
            msg = (
                "Request timed out waiting for Copilot response. "
                "Please try again or check your connection."
            )
            raise GitHubCopilotApiClientCommunicationError(msg) from None
        except ConnectionError as exception:
            LOGGER.error(
                "Connection error during Copilot request (%s).",
                type(exception).__name__,
            )
            # Remove the broken session so it cannot be reused.
            await self._evict_broken_session(session_id)
            msg = "Lost connection to Copilot. Please check your network and try again."
            raise GitHubCopilotApiClientCommunicationError(msg) from None
        except Exception as exception:  # noqa: BLE001 - SDK error boundary.
            LOGGER.error(
                "Copilot request failed (%s).",
                type(exception).__name__,
            )
            msg = "Copilot failed to respond. Check the bridge and MCP server status."
            raise GitHubCopilotApiClientError(msg) from None

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
        LOGGER.debug("Copilot response received.")
        return content

    @staticmethod
    async def _stop_client(client: copilot.CopilotClient) -> None:
        """Stop the SDK without copying potentially sensitive errors into HA logs."""
        try:
            await client.stop()
        except (ExceptionGroup, RuntimeError, OSError) as exception:
            LOGGER.error(
                "Failed to stop Copilot SDK client (%s).", type(exception).__name__
            )
            msg = "Unable to stop the Copilot SDK client."
            raise GitHubCopilotApiClientError(msg) from None

    async def async_close(self) -> None:
        """Close the Copilot SDK client and sessions."""
        async with self._session_lock:
            session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            with suppress(GitHubCopilotApiClientError):
                await self.async_end_session(session_id)
        async with self._client_lock:
            if self._client:
                await self._stop_client(self._client)
                self._client = None
                LOGGER.info("Copilot SDK client stopped.")

    def _check_cli_installed(self) -> CliInstallationStatus:
        """Check if GitHub Copilot CLI is installed and accessible."""
        status = CliInstallationStatus()

        base_suggestions = [
            ("Install the GitHub Copilot CLI: https://docs.github.com/copilot/cli"),
            (
                "Ensure the CLI is in your PATH or set COPILOT_CLI_PATH to its "
                "full path."
            ),
        ]

        raw_cli_candidates = [
            self._client_options.get("cli_path"),
            os.environ.get("COPILOT_CLI_PATH"),
            "copilot",
        ]
        cli_candidates = [
            candidate.strip()
            for candidate in raw_cli_candidates
            if isinstance(candidate, str) and candidate.strip()
        ]
        cli_to_check = cli_candidates[0] if cli_candidates else "copilot"
        explicit_value = next(
            (
                candidate.strip()
                for candidate in raw_cli_candidates[:2]
                if isinstance(candidate, str) and candidate.strip()
            ),
            None,
        )
        explicit_requested = explicit_value is not None

        # Check for copilot CLI in PATH or at an explicit location
        cli_path = shutil.which(cli_to_check)
        explicit_path: Path | None = None
        candidate_path: Path | None = None
        path_parsing_failed = False
        try:
            candidate_path = Path(cli_to_check).expanduser()
        except (ValueError, OSError, RuntimeError) as error:
            status.error_details = (
                f"The configured Copilot CLI path is invalid ({type(error).__name__})"
            )
            path_parsing_failed = True

        if path_parsing_failed:
            status.suggestions = list(base_suggestions)
            return status

        # Defensive checks before using candidate_path
        try:
            if cli_to_check != "copilot" and (
                candidate_path.is_absolute()
                or os.sep in cli_to_check
                or (os.altsep and os.altsep in cli_to_check)
            ):
                explicit_path = candidate_path
        except (AttributeError, OSError, RuntimeError) as error:
            # If any path check fails, treat it as an invalid path
            status.error_details = (
                f"Path validation failed ({type(error).__name__}). "
                "Please provide a valid CLI path."
            )
            status.suggestions = list(base_suggestions)
            return status

        if explicit_requested and explicit_path:
            try:
                if explicit_path.exists():
                    if explicit_path.is_file() and os.access(explicit_path, os.X_OK):
                        cli_path = str(explicit_path)
                    else:
                        status.error_details = (
                            "The configured Copilot CLI path exists but is not "
                            "executable. Adjust permissions (e.g., chmod +x) and retry."
                        )
                        status.suggestions = [
                            *base_suggestions,
                            (
                                "An explicit CLI path was provided; "
                                "ensure it exists and is executable."
                            ),
                        ]
                        return status
            except (OSError, RuntimeError) as error:
                status.error_details = (
                    f"Failed to verify CLI path ({type(error).__name__})"
                )
                status.suggestions = list(base_suggestions)
                return status

        if explicit_requested and not cli_path:
            status.error_details = (
                "The configured Copilot CLI path was not found or is not executable."
            )
            status.suggestions = [
                *base_suggestions,
                (
                    "An explicit CLI path was provided; ensure it exists and is "
                    "executable."
                ),
                (
                    "If running Home Assistant OS, install the CLI inside the core "
                    "container (not only the SSH add-on) and make auth persistent "
                    "with GH_CONFIG_DIR=/config/.gh_config."
                ),
            ]
            return status

        if cli_path:
            status.cli_installed = True
            status.cli_path = cli_path
            status.error_details = ""
        else:
            # Also check common installation locations
            common_paths = [
                Path.home() / ".local" / "bin" / "copilot",
                Path("/usr/local/bin/copilot"),
                Path("/usr/bin/copilot"),
                Path("/config/copilot"),
                Path("/config/bin/copilot"),
            ]
            for path in common_paths:
                try:
                    if path.is_file() and os.access(path, os.X_OK):
                        status.cli_installed = True
                        status.cli_path = str(path)
                        break
                except (OSError, RuntimeError):
                    # If we can't check this path, skip to the next one
                    continue

        if not status.cli_installed:
            status.error_details = status.error_details or (
                "Copilot CLI was not found in PATH or common installation locations "
                "(~/.local/bin/copilot, /usr/local/bin/copilot, /usr/bin/copilot, "
                "/config/copilot, /config/bin/copilot)."
            )
            status.suggestions = [
                *base_suggestions,
                (
                    "If running Home Assistant OS, you can place the CLI binary at "
                    "/config/copilot or /config/bin/copilot to persist across updates."
                ),
                (
                    "Make authentication persistent with "
                    "GH_CONFIG_DIR=/config/.gh_config."
                ),
            ]

        return status

    @staticmethod
    def _format_errno_info(exception: Exception) -> str:
        """
        Format errno info from an exception without exposing path details.

        Args:
            exception: The exception to extract errno from

        Returns:
            A formatted string with errno if available, empty string otherwise

        """
        if hasattr(exception, "errno") and exception.errno:
            return f" (errno: {exception.errno})"
        return ""

    async def _ensure_client(self) -> copilot.CopilotClient:
        """Ensure the Copilot SDK client is started."""
        async with self._client_lock:
            if self._client:
                return self._client

            if not _COPILOT_SDK_AVAILABLE:
                LOGGER.error(
                    "github-copilot-sdk is not installed. %s",
                    _SDK_INSTALL_HINT,
                )
                raise GitHubCopilotApiClientError(_SDK_INSTALL_HINT)

            await self.async_load_mcp_servers()
            cli_url = self._client_options.get("cli_url", "").strip()
            mode = "remote bridge" if cli_url else "local runtime"
            LOGGER.info("Connecting to Copilot CLI (%s).", mode)
            if cli_url:
                connection = copilot.RuntimeConnection.for_uri(cli_url)
            else:
                cli_status = await asyncio.to_thread(self._check_cli_installed)
                explicit_path = self._client_options.get("cli_path") or os.environ.get(
                    "COPILOT_CLI_PATH"
                )
                if explicit_path and not cli_status.cli_installed:
                    LOGGER.error(
                        "GitHub Copilot CLI not found. %s",
                        cli_status.to_user_message(),
                    )
                    msg = (
                        "GitHub Copilot CLI not found. "
                        "Please install it from https://docs.github.com/copilot/cli "
                        "and ensure it's in your PATH."
                    )
                    raise GitHubCopilotApiClientCommunicationError(msg)
                connection = copilot.RuntimeConnection.for_stdio(
                    path=cli_status.cli_path,
                )

            # Initialize the Copilot client
            try:
                # The SDK constructor can download its checksummed CLI runtime.
                client = await asyncio.to_thread(
                    copilot.CopilotClient,
                    connection=connection,
                    github_token=(
                        None if cli_url else self._client_options.get("github_token")
                    ),
                    use_logged_in_user=None if cli_url else False,
                )
            except (TypeError, ValueError) as exception:
                LOGGER.error(
                    "Invalid Copilot client configuration (%s).",
                    type(exception).__name__,
                )
                msg = (
                    "Invalid Copilot client configuration. Please check your settings."
                )
                raise GitHubCopilotApiClientError(msg) from None
            except Exception as exception:  # noqa: BLE001 - SDK error boundary.
                LOGGER.error(
                    "Failed to initialize Copilot client (%s).",
                    type(exception).__name__,
                )
                msg = (
                    "Unable to initialize the Copilot SDK client. "
                    "Check runtime installation and configuration."
                )
                raise GitHubCopilotApiClientError(msg) from None
            try:
                await client.start()
            except FileNotFoundError as exception:
                LOGGER.error(
                    "Copilot CLI executable not found%s.",
                    self._format_errno_info(exception),
                )
                msg = (
                    "GitHub Copilot CLI executable not found. "
                    "Please install it from https://docs.github.com/copilot/cli"
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from None
            except PermissionError as exception:
                LOGGER.error(
                    "Permission denied when starting Copilot CLI%s.",
                    self._format_errno_info(exception),
                )
                msg = (
                    "Permission denied when starting GitHub Copilot CLI. "
                    "Please check file permissions."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from None
            except ConnectionRefusedError as exception:
                LOGGER.error(
                    "Connection refused by Copilot CLI (%s).",
                    type(exception).__name__,
                )
                msg = (
                    "Connection refused by GitHub Copilot CLI. "
                    "The CLI server may not be running or is misconfigured."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from None
            except RuntimeError as exception:
                # The SDK wraps socket.gaierror (DNS failure) in RuntimeError.
                # Detect this case and surface an actionable message.
                cause = exception.__cause__ or exception.__context__
                dns_errnos = {
                    getattr(socket, "EAI_NONAME", -2),  # Name or service not known
                    getattr(socket, "EAI_AGAIN", -3),  # Temporary DNS failure
                    getattr(socket, "EAI_NODATA", -5),  # No address for hostname
                }
                # gaierror may store the code in .errno or args[0]
                cause_errno = (
                    getattr(cause, "errno", None)
                    if isinstance(cause, OSError)
                    else None
                )
                if cause_errno is None and isinstance(cause, OSError) and cause.args:
                    cause_errno = cause.args[0]
                if isinstance(cause, OSError) and cause_errno in dns_errnos:
                    cli_url = self._client_options.get("cli_url", "")
                    # Extract only host[:port] to avoid logging credentials or paths
                    netloc = ""
                    try:
                        parsed = urlparse(cli_url)
                        if parsed.hostname:
                            netloc = (
                                f"{parsed.hostname}:{parsed.port}"
                                if parsed.port
                                else parsed.hostname
                            )
                    except ValueError:
                        pass
                    location = f" '{netloc}'" if netloc else ""
                    LOGGER.error(
                        "DNS resolution failed for Copilot CLI server%s.",
                        location,
                    )
                    msg = (
                        f"Cannot resolve the Copilot CLI server{location}. "
                        "Please verify the bridge add-on is installed and running, "
                        "and that the CLI URL in the integration settings is correct."
                    )
                    raise GitHubCopilotApiClientCommunicationError(msg) from None
                exc_name = type(exception).__name__
                LOGGER.error(
                    "Failed to start Copilot SDK client (%s).",
                    exc_name,
                )
                msg = (
                    "Unable to connect to GitHub Copilot CLI. "
                    "Check the bridge URL, server logs, and network."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from None
            except Exception as exception:  # noqa: BLE001 - SDK error boundary.
                LOGGER.error(
                    "Failed to start Copilot SDK client (%s).",
                    type(exception).__name__,
                )
                msg = (
                    "Unable to connect to GitHub Copilot CLI. "
                    "Check the bridge URL, server logs, and network."
                )
                raise GitHubCopilotApiClientCommunicationError(msg) from None

            LOGGER.info(
                "Copilot transport connected; checking SDK authentication status."
            )
            try:
                auth_status = await client.get_auth_status()
            except Exception as exception:  # noqa: BLE001 - SDK error boundary.
                LOGGER.error(
                    "Unable to query Copilot authentication status (%s).",
                    type(exception).__name__,
                )
                await self._stop_client(client)
                msg = (
                    "Unable to check Copilot authentication status. "
                    "Check the bridge connection and GitHub token configuration."
                )
                raise GitHubCopilotApiClientAuthenticationError(msg) from None

            if not auth_status.isAuthenticated:
                LOGGER.warning(
                    "Copilot SDK reports no authenticated GitHub credentials."
                )
                await self._stop_client(client)
                msg = (
                    "GitHub Copilot CLI is not authenticated. "
                    "Configure a fine-grained GitHub token with Copilot Requests "
                    "permission in the bridge for remote mode, or the integration "
                    "for local mode."
                )
                raise GitHubCopilotApiClientAuthenticationError(msg)

            LOGGER.info(
                "Copilot SDK reports authenticated (%s); "
                "model access is confirmed only when a request succeeds.",
                mode,
            )
            self._client = client
            return client

    async def async_available_models(self) -> Sequence[str]:
        """Return available model IDs from the Copilot SDK."""
        client = await self._ensure_client()
        try:
            models = await client.list_models()
        except Exception as exception:  # noqa: BLE001 - SDK error boundary.
            LOGGER.error(
                "Failed to list Copilot models (%s).",
                type(exception).__name__,
            )
            msg = "Unable to fetch Copilot models."
            raise GitHubCopilotApiClientCommunicationError(msg) from None
        return [model.id for model in models]
