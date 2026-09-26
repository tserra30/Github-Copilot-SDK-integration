"""Model-aware reasoning configuration, persistence, and SDK wire regressions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import get_args
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, PropertyMock, create_autospec, patch

from copilot import CopilotClient, CopilotSession, ModelInfo, RuntimeConnection
from copilot.session import ReasoningEffort

from custom_components.github_copilot import async_setup_entry
from custom_components.github_copilot.api import (
    GitHubCopilotApiClient,
    GitHubCopilotApiClientCommunicationError,
    GitHubCopilotApiClientReasoningError,
)
from custom_components.github_copilot.config_flow import (
    GitHubCopilotFlowHandler,
    GitHubCopilotOptionsFlow,
    _async_reasoning_metadata,
    _client_for_config,
)
from custom_components.github_copilot.const import CONF_REASONING_EFFORT
from custom_components.github_copilot.reasoning import (
    SDK_REASONING_EFFORTS,
    ReasoningCapabilities,
    get_reasoning_capabilities,
)


def model_info(
    model: str = "test-model",
    levels: list[str] | None = None,
    *,
    supported: bool = True,
    default: str | None = None,
) -> ModelInfo:
    """Build the published SDK's metadata shape without querying GitHub."""
    return ModelInfo.from_dict(
        {
            "id": model,
            "name": model,
            "capabilities": {"supports": {"reasoningEffort": supported}},
            "supportedReasoningEfforts": levels,
            "defaultReasoningEffort": default,
        }
    )


def form_result(**kwargs: object) -> dict:
    """Return the rendered schema for assertions without a frontend."""
    return {"type": "form", **kwargs}


def effort_options(result: dict) -> list[str]:
    """Read the actual reasoning selector's offered values."""
    schema = result["data_schema"]
    control = next(
        value
        for key, value in schema.schema.items()
        if str(key) == CONF_REASONING_EFFORT
    )
    return control.config["options"]


class ReasoningMetadataTests(TestCase):
    """Use advertised metadata, not a global assumption about every model."""

    def test_sdk_levels_match_pinned_public_type(self) -> None:
        """Do not claim a level is supported by the SDK when its API omits it."""
        self.assertEqual(SDK_REASONING_EFFORTS, get_args(ReasoningEffort))

    def test_capabilities_preserve_defaults_and_filter_unknown_levels(self) -> None:
        """Expose only model-advertised SDK levels, retaining reported defaults."""
        capabilities = get_reasoning_capabilities(
            [model_info(levels=["none", "low", "high", "future"], default="none")],
            "test-model",
        )
        self.assertTrue(capabilities.known)
        self.assertEqual(capabilities.supported_efforts, ("low", "high"))
        self.assertEqual(capabilities.default_effort, "none")

    def test_non_reasoning_model_and_unknown_metadata_are_distinct(self) -> None:
        """No metadata is not evidence that every reasoning level is allowed."""
        self.assertEqual(
            get_reasoning_capabilities([model_info("auto", supported=False)], "auto"),
            ReasoningCapabilities(known=True),
        )
        self.assertFalse(get_reasoning_capabilities([], "custom-model").known)
        self.assertFalse(get_reasoning_capabilities([model_info()], "test-model").known)


class ReasoningAPITests(IsolatedAsyncioTestCase):
    """Validate overrides and forward them through the supported SDK API."""

    async def asyncSetUp(self) -> None:
        """Create strict SDK mocks with real model metadata."""
        self.sdk = create_autospec(CopilotClient, instance=True)
        self.session = create_autospec(CopilotSession, instance=True)
        self.session.session_id = "reasoning-session"
        self.sdk.create_session.return_value = self.session
        self.sdk.list_models.return_value = [
            model_info(levels=["low", "medium", "high"], default="medium")
        ]

    def _api(self, effort: str | None) -> GitHubCopilotApiClient:
        client = GitHubCopilotApiClient(model="test-model", reasoning_effort=effort)
        client._client = self.sdk  # noqa: SLF001
        return client

    async def test_default_does_not_require_metadata_or_force_low(self) -> None:
        """Old entries retain runtime-controlled effort even if listing fails."""
        self.sdk.list_models.side_effect = RuntimeError("unavailable")
        await self._api(None).async_create_session()
        self.sdk.list_models.assert_not_awaited()
        self.assertIsNone(self.sdk.create_session.call_args.kwargs["reasoning_effort"])

    async def test_explicit_low_is_validated_and_forwarded(self) -> None:
        """A supported override reaches the new SDK session."""
        await self._api("low").async_create_session()
        self.sdk.list_models.assert_awaited_once()
        self.assertEqual(
            self.sdk.create_session.call_args.kwargs["reasoning_effort"], "low"
        )

    async def test_unsupported_or_unknown_levels_never_create_session(self) -> None:
        """No silent downgrade, fallback, or broad unknown-model approval."""
        for effort in ("max", "none", "future", "", "default"):
            with (
                self.subTest(effort=effort),
                self.assertRaises(GitHubCopilotApiClientReasoningError),
            ):
                await self._api(effort).async_create_session()
        self.sdk.create_session.assert_not_awaited()

    async def test_unavailable_capabilities_or_models_block_explicit_effort(
        self,
    ) -> None:
        """An explicit choice cannot be validated using guessed metadata."""
        for models in ([], [model_info()], [model_info(supported=False)]):
            self.sdk.list_models.return_value = models
            with (
                self.subTest(models=models),
                self.assertRaises(GitHubCopilotApiClientReasoningError),
            ):
                await self._api("low").async_create_session()
        self.sdk.list_models.side_effect = RuntimeError("metadata unavailable")
        with self.assertRaises(GitHubCopilotApiClientCommunicationError):
            await self._api("low").async_create_session()
        self.sdk.create_session.assert_not_awaited()

    async def test_catalog_retains_model_capability_metadata(self) -> None:
        """The old ID-list helper remains compatible alongside the rich catalog."""
        client = self._api(None)
        catalog = await client.async_model_catalog()
        self.assertEqual(catalog[0].default_reasoning_effort, "medium")
        self.assertEqual(await client.async_available_models(), ["test-model"])

    async def test_real_sdk_wire_omits_default_and_serializes_low(self) -> None:
        """Exercise the published SDK serializer with only transport mocked."""
        for effort in (None, "low"):
            with self.subTest(effort=effort):
                sdk = CopilotClient(
                    connection=RuntimeConnection.for_uri("http://bridge:8000")
                )
                rpc = Mock()
                rpc.request = AsyncMock(
                    side_effect=[{"sessionId": "reasoning-wire"}, {"success": True}]
                )
                with patch.object(sdk, "_client", rpc):
                    session = await sdk.create_session(
                        session_id="reasoning-wire",
                        reasoning_effort=effort,
                    )
                    payload = rpc.request.call_args.args[1]
                    if effort is None:
                        self.assertNotIn("reasoningEffort", payload)
                    else:
                        self.assertEqual(payload["reasoningEffort"], "low")
                    await session.disconnect()


class ReasoningFlowTests(IsolatedAsyncioTestCase):
    """Both flows use a second, model-specific step without premature writes."""

    async def asyncSetUp(self) -> None:
        """Use candidate inputs and predictable supported levels."""
        self.data = {
            "model": "test-model",
            "cli_url": "http://new-bridge:8000",
            "mcp_config": "",
        }
        self.capabilities = ReasoningCapabilities(
            known=True, supported_efforts=("low", "high"), default_effort="high"
        )

    async def test_setup_selects_effort_before_testing_and_persisting(self) -> None:
        """The connection test receives the chosen effort, not an implicit default."""
        flow = GitHubCopilotFlowHandler()
        with (
            patch(
                "custom_components.github_copilot.config_flow._async_reasoning_metadata",
                return_value=(self.capabilities, None),
            ) as metadata,
            patch.object(flow, "async_show_form", side_effect=form_result),
            patch.object(flow, "_test_credentials") as test_credentials,
            patch.object(flow, "async_set_unique_id"),
            patch.object(flow, "_abort_if_unique_id_configured"),
            patch.object(flow, "async_create_entry") as create_entry,
        ):
            result = await flow.async_step_user(
                {**self.data, "api_token": "unused-remote-value"}
            )
            self.assertEqual(result["step_id"], "reasoning")
            self.assertTrue(result["last_step"])
            self.assertEqual(effort_options(result), ["default", "low", "high"])
            self.assertEqual(
                result["description_placeholders"]["default_effort"], "high"
            )
            test_credentials.assert_not_called()
            create_entry.assert_not_called()
            self.assertEqual(
                metadata.call_args.args[0]["cli_url"], "http://new-bridge:8000"
            )
            await flow.async_step_reasoning({"reasoning_effort": "low"})
        test_credentials.assert_awaited_once()
        self.assertEqual(test_credentials.call_args.kwargs["reasoning_effort"], "low")
        data = create_entry.call_args.kwargs["data"]
        self.assertEqual(data["reasoning_effort"], "low")
        self.assertNotIn("api_token", data)

    async def test_setup_rejects_unsupported_effort_without_credentials_test(
        self,
    ) -> None:
        """Do not test or persist a combination the model does not advertise."""
        flow = GitHubCopilotFlowHandler()
        with (
            patch(
                "custom_components.github_copilot.config_flow._async_reasoning_metadata",
                return_value=(self.capabilities, None),
            ),
            patch.object(flow, "async_show_form", side_effect=form_result),
            patch.object(flow, "_test_credentials") as test_credentials,
        ):
            await flow.async_step_user(self.data)
            result = await flow.async_step_reasoning({"reasoning_effort": "max"})
        self.assertEqual(
            result["errors"]["reasoning_effort"], "unsupported_reasoning_effort"
        )
        test_credentials.assert_not_called()

    async def test_options_model_change_requires_explicit_effort_choice(self) -> None:
        """Changing models cannot silently replace or retain an unsupported effort."""
        flow = GitHubCopilotOptionsFlow()
        entry = SimpleNamespace(
            data={"model": "old-model", "reasoning_effort": "low", "retained": "value"}
        )
        update = Mock()
        flow.hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_update_entry=update)
        )
        with (
            patch.object(
                GitHubCopilotOptionsFlow,
                "config_entry",
                new_callable=PropertyMock,
                return_value=entry,
            ),
            patch(
                "custom_components.github_copilot.config_flow._async_reasoning_metadata",
                return_value=(ReasoningCapabilities(known=True), None),
            ),
            patch.object(flow, "async_show_form", side_effect=form_result),
            patch.object(flow, "async_create_entry"),
        ):
            result = await flow.async_step_init({**self.data, "model": "auto"})
            self.assertEqual(result["step_id"], "reasoning")
            self.assertEqual(
                result["errors"]["reasoning_effort"], "unsupported_reasoning_effort"
            )
            update.assert_not_called()
            await flow.async_step_reasoning({"reasoning_effort": "low"})
            update.assert_not_called()
            await flow.async_step_reasoning({"reasoning_effort": "default"})
        saved = update.call_args.kwargs["data"]
        self.assertEqual(saved["model"], "auto")
        self.assertNotIn("reasoning_effort", saved)
        self.assertEqual(saved["retained"], "value")
        self.assertEqual(entry.data["reasoning_effort"], "low")

    async def test_options_preserve_supported_effort_until_final_submission(
        self,
    ) -> None:
        """Opening or cancelling options never writes candidate configuration."""
        flow = GitHubCopilotOptionsFlow()
        entry = SimpleNamespace(data={**self.data, "reasoning_effort": "low"})
        update = Mock()
        flow.hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_update_entry=update)
        )
        with (
            patch.object(
                GitHubCopilotOptionsFlow,
                "config_entry",
                new_callable=PropertyMock,
                return_value=entry,
            ),
            patch(
                "custom_components.github_copilot.config_flow._async_reasoning_metadata",
                return_value=(self.capabilities, None),
            ),
            patch.object(flow, "async_show_form", side_effect=form_result),
            patch.object(flow, "async_create_entry"),
        ):
            result = await flow.async_step_init({**self.data, "timeout": 240})
            self.assertEqual(result["data_schema"]({})["reasoning_effort"], "low")
            update.assert_not_called()
            await flow.async_step_reasoning({"reasoning_effort": "low"})
        self.assertEqual(update.call_args.kwargs["data"]["reasoning_effort"], "low")
        self.assertEqual(update.call_args.kwargs["data"]["timeout"], 240)

    async def test_metadata_failure_allows_only_explicit_default(self) -> None:
        """Default-only configurations need no reasoning metadata."""
        flow = GitHubCopilotFlowHandler()
        with (
            patch(
                "custom_components.github_copilot.config_flow._async_reasoning_metadata",
                return_value=(
                    ReasoningCapabilities(),
                    "reasoning_metadata_unavailable",
                ),
            ),
            patch.object(flow, "async_show_form", side_effect=form_result),
            patch.object(flow, "_test_credentials") as test_credentials,
            patch.object(flow, "async_set_unique_id"),
            patch.object(flow, "_abort_if_unique_id_configured"),
            patch.object(flow, "async_create_entry") as create_entry,
        ):
            result = await flow.async_step_user(self.data)
            self.assertEqual(effort_options(result), ["default"])
            result = await flow.async_step_reasoning({"reasoning_effort": "low"})
            self.assertEqual(
                result["errors"]["reasoning_effort"], "reasoning_metadata_unavailable"
            )
            test_credentials.assert_not_called()
            await flow.async_step_reasoning({"reasoning_effort": "default"})
        self.assertIsNone(test_credentials.call_args.kwargs["reasoning_effort"])
        self.assertNotIn("reasoning_effort", create_entry.call_args.kwargs["data"])

    async def test_metadata_client_always_closes_and_uses_candidate_connection(
        self,
    ) -> None:
        """Model lookups use the candidate bridge, not stale runtime-data settings."""
        client = Mock()
        client.async_reasoning_capabilities = AsyncMock(return_value=self.capabilities)
        client.async_close = AsyncMock()
        with patch(
            "custom_components.github_copilot.config_flow._client_for_config",
            return_value=client,
        ) as create_client:
            result = await _async_reasoning_metadata(self.data)
            self.assertEqual(result, (self.capabilities, None))
            create_client.assert_called_with(self.data)
            client.async_reasoning_capabilities.side_effect = (
                GitHubCopilotApiClientCommunicationError("unavailable")
            )
            result = await _async_reasoning_metadata(self.data)
            self.assertFalse(result[0].known)
            self.assertEqual(result[1], "reasoning_metadata_unavailable")
        self.assertEqual(client.async_close.await_count, 2)

    async def test_authentication_failure_stays_on_connection_step(self) -> None:
        """Bad credentials can be corrected before the effort-selection step."""
        flow = GitHubCopilotFlowHandler()
        with (
            patch(
                "custom_components.github_copilot.config_flow._async_reasoning_metadata",
                return_value=(ReasoningCapabilities(), "auth"),
            ),
            patch.object(flow, "async_show_form", side_effect=form_result),
        ):
            result = await flow.async_step_user(self.data)
        self.assertEqual(result["step_id"], "user")
        self.assertFalse(result["last_step"])
        self.assertEqual(result["errors"], {"base": "auth"})

    async def test_setup_connection_test_receives_the_selected_effort(self) -> None:
        """The final setup probe uses the same effort as future conversations."""
        flow = GitHubCopilotFlowHandler()
        client = Mock()
        client.async_test_connection = AsyncMock()
        client.async_close = AsyncMock()
        with patch(
            "custom_components.github_copilot.config_flow._client_for_config",
            return_value=client,
        ) as constructor:
            await flow._test_credentials(  # noqa: SLF001
                api_token="",
                model="test-model",
                cli_url="http://bridge:8000",
                reasoning_effort="low",
            )
        self.assertEqual(constructor.call_args.kwargs["reasoning_effort"], "low")
        client.async_test_connection.assert_awaited_once()
        client.async_close.assert_awaited_once()

    async def test_connection_modes_keep_effort_separate_from_credentials(self) -> None:
        """Both local and remote validation clients receive the effort override."""
        with patch(
            "custom_components.github_copilot.config_flow.GitHubCopilotApiClient"
        ) as constructor:
            _client_for_config({**self.data, "api_token": "unused"}, "low")
            self.assertEqual(
                constructor.call_args.kwargs["client_options"],
                {"cli_url": "http://new-bridge:8000"},
            )
            _client_for_config(
                {**self.data, "cli_url": "", "api_token": "local"}, "low"
            )
            self.assertEqual(
                constructor.call_args.kwargs["client_options"],
                {"github_token": "local"},
            )
            self.assertEqual(constructor.call_args.kwargs["reasoning_effort"], "low")


class ReasoningEntryTests(IsolatedAsyncioTestCase):
    """Ensure setup/reload forwards saved data, including legacy absence."""

    async def test_setup_entry_forwards_saved_reasoning_and_preserves_default(
        self,
    ) -> None:
        """Persistence must reach the same client factory used for conversations."""
        for data in (
            {"model": "test-model"},
            {"model": "test-model", "reasoning_effort": "low"},
        ):
            with self.subTest(data=data):
                entry = SimpleNamespace(
                    data=data,
                    domain="github_copilot",
                    async_on_unload=Mock(),
                    add_update_listener=Mock(),
                )
                hass = SimpleNamespace(
                    config_entries=SimpleNamespace(
                        async_forward_entry_setups=AsyncMock(),
                        async_update_entry=Mock(),
                    )
                )
                coordinator = Mock()
                coordinator.async_config_entry_first_refresh = AsyncMock()
                with (
                    patch(
                        "custom_components.github_copilot.GitHubCopilotDataUpdateCoordinator",
                        return_value=coordinator,
                    ),
                    patch(
                        "custom_components.github_copilot.async_get_loaded_integration"
                    ),
                    patch(
                        "custom_components.github_copilot.GitHubCopilotApiClient"
                    ) as constructor,
                ):
                    self.assertTrue(await async_setup_entry(hass, entry))
                self.assertEqual(
                    constructor.call_args.kwargs["reasoning_effort"],
                    data.get("reasoning_effort"),
                )
                hass.config_entries.async_update_entry.assert_not_called()
