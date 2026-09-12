"""Regression tests using the published SDK signatures without network access."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, PropertyMock, create_autospec, patch

from copilot import CopilotClient, CopilotSession, RuntimeConnection
from copilot.client import StdioRuntimeConnection, UriRuntimeConnection
from copilot.rpc import (
    PermissionDecisionApproveOnce,
    PermissionDecisionUserNotAvailable,
)
from copilot.session_events import PermissionRequestMcp

from custom_components.github_copilot.api import (
    CliInstallationStatus,
    GitHubCopilotApiClient,
    GitHubCopilotApiClientCommunicationError,
    GitHubCopilotApiClientError,
)
from custom_components.github_copilot.config_flow import (
    GitHubCopilotFlowHandler,
    GitHubCopilotOptionsFlow,
    _async_validate_mcp_config,
)
from custom_components.github_copilot.conversation import (
    GitHubCopilotConversationEntity,
)
from custom_components.github_copilot.mcp import parse_mcp_config


class CopilotAPITests(IsolatedAsyncioTestCase):
    """Protect MCP forwarding, permission boundaries, and SDK lifecycle calls."""

    async def asyncSetUp(self) -> None:
        """Create strict SDK mocks; no CLI process or model request is made."""
        self.sdk = create_autospec(CopilotClient, instance=True)
        self.session = create_autospec(CopilotSession, instance=True)
        self.session.session_id = "sdk-session"
        self.sdk.create_session.return_value = self.session
        self.sdk.get_auth_status.return_value = SimpleNamespace(isAuthenticated=True)
        self.servers = {
            "ha": {
                "type": "http",
                "url": "http://homeassistant:8123/api/mcp",
                "tools": ["HassTurnOn"],
            }
        }
        self.api = GitHubCopilotApiClient(
            mcp_config=json.dumps({"mcpServers": self.servers})
        )
        await self.api._load_mcp_servers()  # noqa: SLF001
        self.api._client = self.sdk  # noqa: SLF001

    async def test_session_forwards_mcp_and_excludes_builtin_tools(self) -> None:
        """Use keyword arguments recognized by the installed SDK, not 'mcp'."""
        await self.api.async_create_session()
        kwargs = self.sdk.create_session.call_args.kwargs
        self.assertEqual(kwargs["mcp_servers"], self.servers)
        self.assertEqual(kwargs["available_tools"].to_list(), ["mcp:*"])
        self.assertIn("github-mcp-server", kwargs["disabled_mcp_servers"])
        self.assertTrue(callable(kwargs["on_permission_request"]))

    async def test_permissions_enforce_server_and_tool_allowlists(self) -> None:
        """Approve an explicit tool but deny unknown servers and managed requests."""
        invocation = {"session_id": "sdk-session"}
        request = PermissionRequestMcp(
            read_only=False,
            server_name="ha",
            tool_name="HassTurnOn",
            tool_title="Turn on",
        )
        handler = self.api._handle_permission_request  # noqa: SLF001
        self.assertIsInstance(
            handler(request, invocation), PermissionDecisionApproveOnce
        )
        request.tool_name = "HassTurnOff"
        self.assertIsInstance(
            handler(request, invocation), PermissionDecisionUserNotAvailable
        )
        request.tool_name = "HassTurnOn"
        request.server_name = "unknown"
        self.assertIsInstance(
            handler(request, invocation), PermissionDecisionUserNotAvailable
        )
        request.server_name = "ha"
        request.managed_approval_required = True
        self.assertIsInstance(
            handler(request, invocation), PermissionDecisionUserNotAvailable
        )
        request.managed_approval_required = False
        self.assertIsInstance(
            handler(request, {**invocation, "managed_settings_enabled": True}),
            PermissionDecisionUserNotAvailable,
        )

    async def test_empty_tool_allowlist_denies_access(self) -> None:
        """Never turn an empty allowlist into wildcard approval."""
        self.api._mcp_servers["ha"]["tools"] = []  # noqa: SLF001
        request = PermissionRequestMcp(
            read_only=True,
            server_name="ha",
            tool_name="GetLiveContext",
            tool_title="Read state",
        )
        self.assertIsInstance(
            self.api._handle_permission_request(  # noqa: SLF001
                request, {"session_id": "sdk-session"}
            ),
            PermissionDecisionUserNotAvailable,
        )

    async def test_explicit_wildcard_authorizes_only_configured_server(self) -> None:
        """An explicit wildcard still cannot authorize another server's tool."""
        self.api._mcp_servers["ha"]["tools"] = ["*"]  # noqa: SLF001
        request = PermissionRequestMcp(
            read_only=False,
            server_name="ha",
            tool_name="HassTurnOff",
            tool_title="Turn off",
        )
        handler = self.api._handle_permission_request  # noqa: SLF001
        invocation = {"session_id": "sdk-session"}
        self.assertIsInstance(
            handler(request, invocation), PermissionDecisionApproveOnce
        )
        request.server_name = "unknown"
        self.assertIsInstance(
            handler(request, invocation), PermissionDecisionUserNotAvailable
        )

    async def test_prompt_and_session_cleanup_use_current_sdk(self) -> None:
        """Send a string prompt and remove only the owned SDK session."""
        context = await self.api.async_create_session()
        self.session.send_and_wait.return_value = SimpleNamespace(
            data=SimpleNamespace(content="The lamp is on.")
        )
        self.assertEqual(
            await self.api.async_send_prompt(context.session_id, "Turn on the lamp"),
            "The lamp is on.",
        )
        self.session.send_and_wait.assert_awaited_once_with(
            "Turn on the lamp", timeout=120.0
        )
        await self.api.async_end_session(context.session_id)
        self.session.disconnect.assert_awaited_once()
        self.sdk.delete_session.assert_awaited_once_with("sdk-session")

    async def test_timeout_evicts_and_deletes_session(self) -> None:
        """A timed-out session cannot be reused or keep its persisted state."""
        context = await self.api.async_create_session()
        self.session.send_and_wait.side_effect = TimeoutError
        with self.assertRaises(GitHubCopilotApiClientCommunicationError):
            await self.api.async_send_prompt(context.session_id, "Read the lamp")
        self.session.disconnect.assert_awaited_once()
        self.sdk.delete_session.assert_awaited_once_with("sdk-session")
        with self.assertRaisesRegex(GitHubCopilotApiClientError, "not found"):
            await self.api.async_send_prompt(context.session_id, "Try again")

    async def test_sdk_error_is_not_a_success_response(self) -> None:
        """Surface session.error exceptions raised by SDK send_and_wait."""
        context = await self.api.async_create_session()
        self.session.send_and_wait.side_effect = RuntimeError("MCP unavailable")
        with self.assertRaisesRegex(GitHubCopilotApiClientError, "MCP unavailable"):
            await self.api.async_send_prompt(context.session_id, "Read the lamp")

    async def test_remote_client_does_not_receive_token_or_download_cli(self) -> None:
        """Remote mode uses a URI connection and ignores local token/path settings."""
        api = GitHubCopilotApiClient(
            client_options={"cli_url": "http://bridge:8000", "github_token": "unused"}
        )
        with (
            patch(
                "custom_components.github_copilot.api.copilot.CopilotClient",
                autospec=True,
                return_value=self.sdk,
            ) as constructor,
            patch.object(api, "_check_cli_installed") as cli_check,
        ):
            await api.async_create_session()
        kwargs = constructor.call_args.kwargs
        self.assertIsInstance(kwargs["connection"], UriRuntimeConnection)
        self.assertEqual(kwargs["connection"].url, "http://bridge:8000")
        self.assertIsNone(kwargs["github_token"])
        cli_check.assert_not_called()

    async def test_local_mode_allows_sdk_runtime_download(self) -> None:
        """An absent standalone CLI does not block the official SDK downloader."""
        api = GitHubCopilotApiClient(client_options={"github_token": "example"})
        with (
            patch.dict("os.environ", {"COPILOT_CLI_PATH": ""}),
            patch.object(
                api, "_check_cli_installed", return_value=CliInstallationStatus()
            ),
            patch(
                "custom_components.github_copilot.api.copilot.CopilotClient",
                autospec=True,
                return_value=self.sdk,
            ) as constructor,
        ):
            await api.async_create_session()
        kwargs = constructor.call_args.kwargs
        self.assertIsInstance(kwargs["connection"], StdioRuntimeConnection)
        self.assertIsNone(kwargs["connection"].path)
        self.assertEqual(kwargs["github_token"], "example")
        self.assertFalse(kwargs["use_logged_in_user"])

    async def test_invalid_config_fails_before_connecting(self) -> None:
        """Setup and runtime share configuration validation."""
        self.assertFalse(await _async_validate_mcp_config('{"mcpServers":null}'))
        api = GitHubCopilotApiClient(mcp_config='{"mcpServers":null}')
        with (
            patch(
                "custom_components.github_copilot.api.copilot.CopilotClient"
            ) as constructor,
            self.assertRaisesRegex(GitHubCopilotApiClientError, "Invalid MCP"),
        ):
            await api.async_create_session()
        constructor.assert_not_called()

    async def test_missing_tools_fails_before_connecting(self) -> None:
        """Reject legacy implicit authorization before any SDK client is created."""
        config = '{"mcpServers":{"ha":{"type":"http","url":"http://host/mcp"}}}'
        self.assertFalse(await _async_validate_mcp_config(config))
        api = GitHubCopilotApiClient(mcp_config=config)
        with (
            patch(
                "custom_components.github_copilot.api.copilot.CopilotClient"
            ) as constructor,
            self.assertRaisesRegex(GitHubCopilotApiClientError, "Invalid MCP"),
        ):
            await api.async_create_session()
        constructor.assert_not_called()

    async def test_setup_and_options_reject_missing_tools(self) -> None:
        """Both HA forms reject implicit authorization without persisting it."""
        user_input = {
            "model": "auto",
            "cli_url": "http://bridge:8000",
            "mcp_config": '{"mcpServers":{"ha":{"url":"http://host/mcp"}}}',
        }
        setup = GitHubCopilotFlowHandler()
        with (
            patch.object(setup, "async_show_form") as show_setup,
            patch.object(setup, "_test_credentials") as test_credentials,
        ):
            await setup.async_step_user(user_input)
        self.assertEqual(
            show_setup.call_args.kwargs["errors"], {"mcp_config": "invalid_mcp"}
        )
        test_credentials.assert_not_called()

        options = GitHubCopilotOptionsFlow()
        update_entry = Mock()
        options.hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_update_entry=update_entry)
        )
        entry = SimpleNamespace(
            data={},
            runtime_data=SimpleNamespace(
                client=SimpleNamespace(
                    async_available_models=AsyncMock(return_value=["auto"])
                )
            ),
        )
        with (
            patch.object(
                GitHubCopilotOptionsFlow,
                "config_entry",
                new_callable=PropertyMock,
                return_value=entry,
            ),
            patch.object(options, "async_show_form") as show_options,
        ):
            await options.async_step_init(user_input)
        self.assertEqual(
            show_options.call_args.kwargs["errors"], {"mcp_config": "invalid_mcp"}
        )
        update_entry.assert_not_called()

    async def test_published_sdk_serializes_local_working_directory(self) -> None:
        """Exercise the real SDK session serializer, mocking only RPC transport."""
        for directory_key in ("cwd", "working_directory"):
            with self.subTest(directory_key=directory_key):
                servers = parse_mcp_config(
                    json.dumps(
                        {
                            "mcpServers": {
                                "local": {
                                    "command": "example",
                                    directory_key: "/config/mcp-server",
                                    "tools": [],
                                }
                            }
                        }
                    )
                )
                client = CopilotClient(
                    connection=RuntimeConnection.for_uri("http://bridge:8000")
                )
                rpc = Mock()
                rpc.request = AsyncMock(
                    side_effect=[{"sessionId": "sdk-session"}, {"success": True}]
                )
                with patch.object(client, "_client", rpc):
                    session = await client.create_session(
                        session_id="sdk-session", mcp_servers=servers
                    )
                    method, payload = rpc.request.call_args.args
                    self.assertEqual(method, "session.create")
                    self.assertEqual(
                        payload["mcpServers"]["local"]["cwd"], "/config/mcp-server"
                    )
                    self.assertNotIn(
                        "working_directory", payload["mcpServers"]["local"]
                    )
                    await session.disconnect()
                self.assertEqual(
                    servers["local"]["working_directory"], "/config/mcp-server"
                )
                self.assertNotIn("cwd", servers["local"])

    async def test_entity_cleanup_uses_sdk_not_ha_conversation_id(self) -> None:
        """Expiry and unload clean up the actual SDK session, not the HA ID."""
        context = await self.api.async_create_session()
        entry = SimpleNamespace(
            entry_id="entry",
            data={},
            runtime_data=SimpleNamespace(client=self.api),
        )
        entity = GitHubCopilotConversationEntity(entry)
        entity.sessions["ha-conversation"] = context
        entity._session_last_used["ha-conversation"] = 0  # noqa: SLF001
        await entity._cleanup_expired_sessions()  # noqa: SLF001
        self.sdk.delete_session.assert_awaited_once_with("sdk-session")
        self.assertFalse(entity.sessions)

    async def test_conversation_error_is_reported_as_error(self) -> None:
        """An integration failure must not look like a successful HA action."""
        entity = GitHubCopilotConversationEntity(
            SimpleNamespace(entry_id="entry", data={})
        )
        result = entity._create_error_result(  # noqa: SLF001
            "en", "conversation", "MCP unavailable"
        )
        self.assertEqual(result.response.response_type.value, "error")

    async def test_mcp_configuration_advertises_control_to_assist(self) -> None:
        """Avoid Assist's misleading no-home-control warning when MCP is enabled."""
        for config, expected in (("", 0), ("@/config/mcp.json", 1)):
            with self.subTest(config=config):
                entity = GitHubCopilotConversationEntity(
                    SimpleNamespace(entry_id="entry", data={"mcp_config": config})
                )
                self.assertEqual(entity.supported_features, expected)
