"""Conversation platform for GitHub Copilot integration."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Literal

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent
from homeassistant.util import ulid

from .api import (
    CopilotSessionContext,
    GitHubCopilotApiClientAuthenticationError,
    GitHubCopilotApiClientCommunicationError,
    GitHubCopilotApiClientError,
)
from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GitHub Copilot conversation platform via config entry."""
    try:
        agent = GitHubCopilotConversationEntity(config_entry)
        async_add_entities([agent])
        LOGGER.debug("GitHub Copilot conversation entity setup completed")
    except Exception as err:
        # Don't log exception details to avoid exposing sensitive data
        # such as config data, API credentials, or user information
        LOGGER.error(
            "Failed to set up GitHub Copilot conversation entity: %s",
            type(err).__name__,
        )
        raise


class GitHubCopilotConversationEntity(conversation.ConversationEntity):
    """GitHub Copilot conversation agent."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = config_entry
        self._attr_name = "GitHub Copilot"
        self._attr_unique_id = f"{config_entry.entry_id}-conversation"
        self.sessions: dict[str, CopilotSessionContext] = {}
        self._session_last_used: dict[str, float] = {}
        # Session timeout: 1 hour of inactivity
        self._session_timeout = 3600

    async def async_will_remove_from_hass(self) -> None:
        """Clean up sessions when entity is removed."""
        LOGGER.debug("Cleaning up %d Copilot sessions", len(self.sessions))
        client = None
        try:
            client = self.entry.runtime_data.client
        except AttributeError:
            LOGGER.warning(
                "Unable to access client during cleanup - may have been removed"
            )
            return

        # Clean up all sessions
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            try:
                await client.async_end_session(session_id)
                LOGGER.debug("Cleaned up session %s", session_id)
            except Exception as err:  # noqa: BLE001
                LOGGER.error(
                    "Failed to clean up session %s: %s",
                    session_id,
                    type(err).__name__,
                )
        self.sessions.clear()
        self._session_last_used.clear()

    async def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions that haven't been used recently."""
        current_time = time.time()
        expired_sessions = [
            session_id
            for session_id, last_used in self._session_last_used.items()
            if current_time - last_used > self._session_timeout
        ]

        if not expired_sessions:
            return

        LOGGER.debug("Cleaning up %d expired sessions", len(expired_sessions))
        try:
            client = self.entry.runtime_data.client
        except AttributeError:
            LOGGER.warning("Unable to access client for session cleanup")
            return

        for session_id in expired_sessions:
            try:
                await client.async_end_session(session_id)
                self.sessions.pop(session_id, None)
                self._session_last_used.pop(session_id, None)
                LOGGER.debug("Expired session %s cleaned up", session_id)
            except Exception as err:  # noqa: BLE001
                LOGGER.error(
                    "Failed to cleanup expired session %s: %s",
                    session_id,
                    type(err).__name__,
                )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    def _create_error_result(
        self,
        language: str,
        conversation_id: str,
        message: str,
    ) -> conversation.ConversationResult:
        """Create an error response result."""
        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_speech(message)
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )

    async def _ensure_session(
        self,
        conversation_id: str,
        language: str,
    ) -> tuple[CopilotSessionContext | None, conversation.ConversationResult | None]:
        """Ensure a session exists, returning session and optional error result."""
        # Clean up expired sessions periodically
        await self._cleanup_expired_sessions()

        if conversation_id in self.sessions:
            # Update last used timestamp
            self._session_last_used[conversation_id] = time.time()
            return self.sessions[conversation_id], None

        error_result: conversation.ConversationResult | None = None
        session_context: CopilotSessionContext | None = None
        try:
            client = self.entry.runtime_data.client
            session_context = await client.async_create_session()
            self.sessions[conversation_id] = session_context
            self._session_last_used[conversation_id] = time.time()
        except GitHubCopilotApiClientAuthenticationError as err:
            LOGGER.error("Authentication error creating session: %s", err)
            error_result = self._create_error_result(
                language,
                conversation_id,
                "GitHub Copilot authentication failed. "
                "Please check your GitHub token and ensure you have "
                "an active Copilot subscription.",
            )
        except GitHubCopilotApiClientCommunicationError as err:
            LOGGER.error("Communication error creating session: %s", err)
            error_result = self._create_error_result(
                language,
                conversation_id,
                "Unable to connect to GitHub Copilot. "
                "Please check if the Copilot CLI is installed and running, "
                "and verify your network connection.",
            )
        except GitHubCopilotApiClientError as err:
            LOGGER.error("Error creating session: %s", err)
            error_result = self._create_error_result(
                language,
                conversation_id,
                "Failed to start a conversation with GitHub Copilot. "
                "Please check the logs for more details.",
            )
        return session_context, error_result

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        conversation_id = user_input.conversation_id or ulid.ulid_now()
        result: conversation.ConversationResult | None = None

        # Safely access runtime_data and client
        try:
            client = self.entry.runtime_data.client
        except AttributeError as err:
            LOGGER.error(
                "Failed to access API client - integration may be incomplete: %s",
                err,
            )
            return self._create_error_result(
                user_input.language,
                conversation_id,
                "The GitHub Copilot integration is not properly initialized. "
                "Please check the logs and try reloading the integration.",
            )

        # Create session if needed
        session_context, error_result = await self._ensure_session(
            conversation_id,
            user_input.language,
        )
        if error_result:
            return error_result

        # Guard against None session_context (should not happen, but be defensive)
        if session_context is None:
            LOGGER.error("Session context is None after successful session creation")
            return self._create_error_result(
                user_input.language,
                conversation_id,
                "Internal error: session initialization failed. "
                "Please try again or reload the integration.",
            )

        # Send the prompt and get response
        try:
            response_text = await client.async_send_prompt(
                session_context.session_id,
                user_input.text,
            )
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(response_text)
            result = conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )
        except GitHubCopilotApiClientAuthenticationError as err:
            LOGGER.error("Authentication error during conversation: %s", err)
            self.sessions.pop(conversation_id, None)
            self._session_last_used.pop(conversation_id, None)
            result = self._create_error_result(
                user_input.language,
                conversation_id,
                "GitHub Copilot session expired or authentication failed. "
                "Please reload the integration and try again.",
            )
        except GitHubCopilotApiClientCommunicationError as err:
            LOGGER.error("Communication error during conversation: %s", err)
            self.sessions.pop(conversation_id, None)
            self._session_last_used.pop(conversation_id, None)
            result = self._create_error_result(
                user_input.language,
                conversation_id,
                "Lost connection to GitHub Copilot. "
                "Please check your network and try again.",
            )
        except GitHubCopilotApiClientError as err:
            LOGGER.error("Error processing conversation: %s", err)
            self.sessions.pop(conversation_id, None)
            self._session_last_used.pop(conversation_id, None)
            result = self._create_error_result(
                user_input.language,
                conversation_id,
                "Sorry, GitHub Copilot encountered an error. "
                "Please try again or check the logs for details.",
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.error(
                "Unexpected error processing conversation: %s - %s",
                type(err).__name__,
                str(err),
            )
            result = self._create_error_result(
                user_input.language,
                conversation_id,
                "Sorry, an unexpected error occurred. "
                "Please check the Home Assistant logs for details.",
            )
        return result
