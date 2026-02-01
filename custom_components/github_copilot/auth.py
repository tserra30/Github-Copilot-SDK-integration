"""GitHub Copilot OAuth authentication module.

This module handles the GitHub OAuth device flow authentication
and token management for GitHub Copilot API access.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiohttp

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# GitHub OAuth endpoints
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"

# GitHub Copilot OAuth client ID (public client ID used by official clients)
# This is the same client ID used by VS Code and other official Copilot clients
GITHUB_COPILOT_CLIENT_ID = "Iv1.b507a08c87ecfe98"

# Required scopes for Copilot API access
GITHUB_COPILOT_SCOPES = "read:user"


class GitHubAuthError(Exception):
    """Base exception for GitHub authentication errors."""


class GitHubAuthTimeoutError(GitHubAuthError):
    """Exception raised when device flow times out."""


class GitHubAuthDeniedError(GitHubAuthError):
    """Exception raised when user denies authorization."""


class GitHubAuthDeviceFlowDisabledError(GitHubAuthError):
    """Exception raised when device flow is disabled."""


@dataclass
class DeviceCodeResponse:
    """Response from device code request."""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass
class GitHubToken:
    """GitHub OAuth token data."""

    access_token: str
    token_type: str
    scope: str


@dataclass
class CopilotToken:
    """GitHub Copilot API token data."""

    token: str
    expires_at: int
    refresh_in: int

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        # Add 60 second buffer before expiration
        return time.time() >= (self.expires_at - 60)

    @property
    def should_refresh(self) -> bool:
        """Check if the token should be refreshed."""
        return time.time() >= self.refresh_in


class GitHubCopilotAuth:
    """Handle GitHub Copilot OAuth authentication."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the authentication handler."""
        self._hass = hass
        self._session = session
        self._github_token: GitHubToken | None = None
        self._copilot_token: CopilotToken | None = None

    async def start_device_flow(self) -> DeviceCodeResponse:
        """Start the OAuth device flow.

        Returns:
            DeviceCodeResponse containing the user code and verification URL.

        Raises:
            GitHubAuthError: If the device flow request fails.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "client_id": GITHUB_COPILOT_CLIENT_ID,
            "scope": GITHUB_COPILOT_SCOPES,
        }

        try:
            async with self._session.post(
                GITHUB_DEVICE_CODE_URL,
                headers=headers,
                json=data,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    LOGGER.error(
                        "Device code request failed: %s - %s",
                        response.status,
                        error_text,
                    )
                    raise GitHubAuthError(
                        f"Failed to start device flow: HTTP {response.status}"
                    )

                result = await response.json()
                LOGGER.debug("Device code response: %s", result)

                if "error" in result:
                    error = result.get("error")
                    if error == "device_flow_disabled":
                        raise GitHubAuthDeviceFlowDisabledError(
                            "Device flow is not enabled for this OAuth app"
                        )
                    raise GitHubAuthError(
                        f"Device flow error: {result.get('error_description', error)}"
                    )

                return DeviceCodeResponse(
                    device_code=result["device_code"],
                    user_code=result["user_code"],
                    verification_uri=result["verification_uri"],
                    expires_in=result["expires_in"],
                    interval=result["interval"],
                )

        except aiohttp.ClientError as err:
            LOGGER.exception("Network error during device flow start")
            raise GitHubAuthError(f"Network error: {err}") from err

    async def poll_for_token(
        self,
        device_code: str,
        interval: int,
        expires_in: int,
    ) -> GitHubToken:
        """Poll for the access token after user authorizes.

        Args:
            device_code: The device code from start_device_flow.
            interval: Minimum seconds between poll requests.
            expires_in: Seconds until the device code expires.

        Returns:
            GitHubToken containing the access token.

        Raises:
            GitHubAuthTimeoutError: If the device code expires.
            GitHubAuthDeniedError: If the user denies authorization.
            GitHubAuthError: For other authentication errors.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "client_id": GITHUB_COPILOT_CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }

        start_time = time.time()
        current_interval = interval

        while (time.time() - start_time) < expires_in:
            await asyncio.sleep(current_interval)

            try:
                async with self._session.post(
                    GITHUB_ACCESS_TOKEN_URL,
                    headers=headers,
                    json=data,
                ) as response:
                    result = await response.json()
                    LOGGER.debug("Token poll response: %s", result)

                    if "error" in result:
                        error = result.get("error")

                        if error == "authorization_pending":
                            # User hasn't authorized yet, continue polling
                            continue

                        if error == "slow_down":
                            # Increase interval as requested
                            current_interval = result.get(
                                "interval", current_interval + 5
                            )
                            LOGGER.debug(
                                "Slowing down polling to %s seconds", current_interval
                            )
                            continue

                        if error == "expired_token":
                            raise GitHubAuthTimeoutError(
                                "Device code expired. Please try again."
                            )

                        if error == "access_denied":
                            raise GitHubAuthDeniedError(
                                "Authorization was denied by the user."
                            )

                        raise GitHubAuthError(
                            f"Authentication error: "
                            f"{result.get('error_description', error)}"
                        )

                    # Success! We have a token
                    token = GitHubToken(
                        access_token=result["access_token"],
                        token_type=result.get("token_type", "bearer"),
                        scope=result.get("scope", ""),
                    )
                    self._github_token = token
                    return token

            except aiohttp.ClientError as err:
                LOGGER.warning("Network error during token poll: %s", err)
                # Continue polling on network errors
                continue

        raise GitHubAuthTimeoutError("Device code expired. Please try again.")

    async def get_copilot_token(
        self,
        github_token: str | None = None,
    ) -> CopilotToken:
        """Get or refresh the Copilot API token.

        The Copilot API requires a separate token that is obtained using
        the GitHub OAuth token. This token has a shorter lifespan and
        needs to be refreshed periodically.

        Args:
            github_token: Optional GitHub OAuth token. Uses stored token if not provided.

        Returns:
            CopilotToken for API access.

        Raises:
            GitHubAuthError: If token retrieval fails.
        """
        token = github_token or (
            self._github_token.access_token if self._github_token else None
        )

        if not token:
            raise GitHubAuthError("No GitHub token available")

        # Check if we have a valid cached Copilot token
        if self._copilot_token and not self._copilot_token.is_expired:
            return self._copilot_token

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/json",
        }

        try:
            async with self._session.get(
                GITHUB_COPILOT_TOKEN_URL,
                headers=headers,
            ) as response:
                if response.status == 401:
                    raise GitHubAuthError(
                        "GitHub token is invalid or expired. Please re-authenticate."
                    )

                if response.status == 403:
                    error_text = await response.text()
                    LOGGER.error("Copilot access forbidden: %s", error_text)
                    raise GitHubAuthError(
                        "Access to GitHub Copilot denied. "
                        "Please ensure you have an active Copilot subscription."
                    )

                if response.status != 200:
                    error_text = await response.text()
                    LOGGER.error(
                        "Copilot token request failed: %s - %s",
                        response.status,
                        error_text,
                    )
                    raise GitHubAuthError(
                        f"Failed to get Copilot token: HTTP {response.status}"
                    )

                result = await response.json()
                LOGGER.debug("Copilot token response received (token redacted)")

                copilot_token = CopilotToken(
                    token=result["token"],
                    expires_at=result["expires_at"],
                    refresh_in=result.get(
                        "refresh_in",
                        result["expires_at"] - 300,  # Default: 5 min before expiry
                    ),
                )
                self._copilot_token = copilot_token
                return copilot_token

        except aiohttp.ClientError as err:
            LOGGER.exception("Network error getting Copilot token")
            raise GitHubAuthError(f"Network error: {err}") from err

    async def validate_github_token(self, token: str) -> bool:
        """Validate a GitHub OAuth token by attempting to get a Copilot token.

        Args:
            token: The GitHub OAuth access token to validate.

        Returns:
            True if the token is valid and has Copilot access.

        Raises:
            GitHubAuthError: If validation fails.
        """
        try:
            await self.get_copilot_token(token)
            return True
        except GitHubAuthError:
            raise

    def set_github_token(self, token: GitHubToken) -> None:
        """Set the GitHub OAuth token."""
        self._github_token = token
        # Clear cached Copilot token when GitHub token changes
        self._copilot_token = None

    def clear_tokens(self) -> None:
        """Clear all cached tokens."""
        self._github_token = None
        self._copilot_token = None

    @property
    def has_valid_github_token(self) -> bool:
        """Check if we have a GitHub token stored."""
        return self._github_token is not None

    @property
    def github_token(self) -> str | None:
        """Get the current GitHub OAuth token."""
        return self._github_token.access_token if self._github_token else None
