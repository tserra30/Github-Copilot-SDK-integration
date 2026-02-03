"""Conversation platform for GitHub Copilot integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent
from homeassistant.util import ulid

from .const import LOGGER, MAX_HISTORY_MESSAGES

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
        LOGGER.exception("Failed to set up GitHub Copilot conversation entity: %s", err)
        raise


class GitHubCopilotConversationEntity(conversation.ConversationEntity):
    """GitHub Copilot conversation agent."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = config_entry
        self._attr_name = "GitHub Copilot"
        self._attr_unique_id = f"{config_entry.entry_id}-conversation"
        self.history: dict[str, list[dict]] = {}

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
        if conversation_id not in self.history:
            self.history[conversation_id] = []

        # Add user message to history
        self.history[conversation_id].append(
            {
                "role": "user",
                "content": user_input.text,
            }
        )

        # Keep only last messages to avoid token limits
        if len(self.history[conversation_id]) > MAX_HISTORY_MESSAGES:
            self.history[conversation_id] = self.history[conversation_id][
                -MAX_HISTORY_MESSAGES:
            ]

        try:
            # Call GitHub Copilot API
            msg_count = len(self.history.get(conversation_id, []))
            LOGGER.debug("Sending %d messages to API", msg_count)
            response = await client.async_chat(self.history[conversation_id])
            LOGGER.debug("Received API response: %s", response)

            # Check for error response from API
            if "error" in response:
                error_msg = response.get("error", {}).get("message", "Unknown error")
                LOGGER.error("API error response: %s", error_msg)
                LOGGER.debug("Full error response: %s", response)
                # Remove the failed user message from history
                if self.history.get(conversation_id):
                    self.history[conversation_id].pop()
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_speech(f"API Error: {error_msg}")
                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=conversation_id,
                )

            # Extract response text - handle various response formats
            choices = response.get("choices", [])
            if not choices:
                LOGGER.warning("No choices in API response")
                LOGGER.debug("Full API response without choices: %s", response)
                # Remove the failed user message from history
                if self.history.get(conversation_id):
                    self.history[conversation_id].pop()
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_speech(
                    "No response received from the API. Please try again."
                )
                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=conversation_id,
                )

            assistant_message = choices[0].get("message", {}).get("content", "")

            if not assistant_message:
                LOGGER.warning("Empty content in API response")
                message_structure = choices[0].get("message", {})
                LOGGER.debug("Full message structure: %s", message_structure)
                assistant_message = "I received an empty response. Please try again."

            # Add assistant response to history
            self.history[conversation_id].append(
                {
                    "role": "assistant",
                    "content": assistant_message,
                }
            )

            # Create intent response
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(assistant_message)

            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )

        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Error processing conversation: %s", err)
            # Remove the failed user message from history to avoid corrupting history
            if self.history.get(conversation_id):
                self.history[conversation_id].pop()
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                "Sorry, an error occurred while processing your request. "
                "Please check the logs for more details."
            )
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )
