"""Conversation platform for GitHub Copilot integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent
from homeassistant.util import ulid

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
        self.sessions: dict[str, object] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        # Get or create conversation history for this conversation_id
        conversation_id = user_input.conversation_id or ulid.ulid_now()

        # Safely access runtime_data and client
        try:
            client = self.entry.runtime_data.client
        except AttributeError as err:
            LOGGER.error(
                "Failed to access API client - integration setup may be incomplete: %s",
                err,
            )
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                "The integration is not properly initialized. "
                "Please check the logs and try reloading the integration."
            )
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )
        if conversation_id not in self.sessions:
            session_context = await client.async_create_session()
            self.sessions[conversation_id] = session_context

        try:
            session_context = self.sessions[conversation_id]
            response_text = await client.async_send_prompt(
                session_context.session_id,
                user_input.text,
            )
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(response_text)

            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )

        except Exception as err:  # noqa: BLE001
            # Don't log exception details to avoid exposing sensitive
            # user data or tokens
            LOGGER.error(
                "Error processing conversation: %s",
                type(err).__name__,
            )
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                "Sorry, an error occurred while processing your request. "
                "Please check the logs for more details."
            )
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )
