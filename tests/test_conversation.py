"""Regression coverage for effective MCP capabilities exposed to Assist."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from custom_components.github_copilot.api import (
    GitHubCopilotApiClient,
    GitHubCopilotApiClientError,
)
from custom_components.github_copilot.conversation import async_setup_entry


class ConversationCapabilityTests(IsolatedAsyncioTestCase):
    """Only validated configurations with authorized tools advertise CONTROL."""

    async def test_control_uses_effective_inline_and_file_configuration(self) -> None:
        """Empty, deny-all, named, and wildcard tools work identically in files."""
        remote = {"type": "http", "url": "http://homeassistant:8123/api/mcp"}
        local = {"command": "example"}
        cases = [
            ("", False),
            ('{"mcpServers":{}}', False),
        ]
        cases.extend(
            (
                json.dumps({"mcpServers": {"ha": {**server, "tools": tools}}}),
                bool(tools),
            )
            for server in (remote, local)
            for tools in ([], ["intent__HassTurnOn"], ["*"])
        )
        cases.append(
            (
                json.dumps(
                    {
                        "mcpServers": {
                            "denied": {**remote, "tools": []},
                            "allowed": {**local, "tools": ["example"]},
                        }
                    }
                ),
                True,
            )
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.json"
            for config, expected in cases:
                path.write_text(config, encoding="utf-8")
                for value in (config, str(path), f"@{path}"):
                    with self.subTest(config=config, value=value):
                        client = GitHubCopilotApiClient(mcp_config=value)
                        entry = SimpleNamespace(
                            entry_id="entry",
                            data={"mcp_config": value},
                            runtime_data=SimpleNamespace(client=client),
                        )
                        add_entities = Mock()
                        with patch(
                            "custom_components.github_copilot.api.copilot.CopilotClient"
                        ) as sdk:
                            await async_setup_entry(Mock(), entry, add_entities)
                        sdk.assert_not_called()
                        entity = add_entities.call_args.args[0][0]
                        self.assertEqual(client.has_mcp_tools, expected)
                        self.assertEqual(entity.supported_features, int(expected))

    async def test_invalid_file_never_creates_control_capable_entity(self) -> None:
        """Missing files and invalid definitions fail setup, not silently disable."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.json"
            for contents in (None, "{", '{"mcpServers":{"ha":{"command":"example"}}}'):
                with self.subTest(contents=contents):
                    if contents is not None:
                        path.write_text(contents, encoding="utf-8")
                    client = GitHubCopilotApiClient(mcp_config=f"@{path}")
                    entry = SimpleNamespace(
                        entry_id="entry",
                        data={"mcp_config": f"@{path}"},
                        runtime_data=SimpleNamespace(client=client),
                    )
                    add_entities = Mock()
                    with self.assertRaises(GitHubCopilotApiClientError):
                        await async_setup_entry(Mock(), entry, add_entities)
                    add_entities.assert_not_called()
                    self.assertFalse(client.has_mcp_tools)

    async def test_capabilities_and_permissions_share_configuration_until_reload(
        self,
    ) -> None:
        """A file edit cannot change authorization behind Assist's capability flag."""
        config = '{"mcpServers":{"ha":{"command":"example","tools":["allowed"]}}}'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.json"
            path.write_text(config, encoding="utf-8")
            client = GitHubCopilotApiClient(mcp_config=f"@{path}")
            await client.async_load_mcp_servers()
            path.write_text('{"mcpServers":{}}', encoding="utf-8")
            await client.async_load_mcp_servers()
            self.assertTrue(client.has_mcp_tools)
            allowed_tools = client._mcp_servers["ha"]["tools"]  # noqa: SLF001
            self.assertEqual(allowed_tools, ["allowed"])
            reloaded = GitHubCopilotApiClient(mcp_config=f"@{path}")
            await reloaded.async_load_mcp_servers()
            self.assertFalse(reloaded.has_mcp_tools)
