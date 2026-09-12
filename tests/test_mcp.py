"""Regression coverage for MCP configuration and legacy aliases."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase

from custom_components.github_copilot.mcp import (
    async_load_mcp_config,
    parse_mcp_config,
)


class MCPConfigurationTests(TestCase):
    """Exercise the exact JSON accepted by the SDK session configuration."""

    def test_remote_transport_alias(self) -> None:
        """Normalize previously documented streamable HTTP configurations."""
        config = parse_mcp_config(
            json.dumps(
                {
                    "mcpServers": {
                        "ha": {
                            "transport": "streamable-http",
                            "url": "http://homeassistant:8123/api/mcp",
                            "tools": ["*"],
                            "headers": {"Authorization": "Bearer example"},
                        }
                    }
                }
            )
        )
        self.assertEqual(config["ha"]["type"], "http")
        self.assertEqual(config["ha"]["tools"], ["*"])
        self.assertNotIn("transport", config["ha"])

    def test_local_directory_alias_and_empty_allowlist(self) -> None:
        """Preserve an explicit deny-all list and normalize the SDK directory key."""
        config = parse_mcp_config(
            '{"mcpServers":{"local":{"command":"example","cwd":"/config","tools":[]}}}'
        )
        self.assertEqual(config["local"]["working_directory"], "/config")
        self.assertEqual(config["local"]["args"], [])
        self.assertEqual(config["local"]["tools"], [])
        self.assertNotIn("cwd", config["local"])

    def test_servers_require_explicit_tools(self) -> None:
        """A server address or command alone must not authorize any tools."""
        for server in (
            {"type": "http", "url": "http://host/mcp"},
            {"type": "sse", "url": "http://host/sse"},
            {"type": "local", "command": "example"},
            {"type": "stdio", "command": "example"},
        ):
            with (
                self.subTest(server=server),
                self.assertRaisesRegex(ValueError, "explicit tools list"),
            ):
                parse_mcp_config(json.dumps({"mcpServers": {"test": server}}))

    def test_explicit_tool_lists_are_preserved(self) -> None:
        """Respect explicit deny-all, named tools, and wildcard authorization."""
        for tools in ([], ["GetLiveContext"], ["*"]):
            for server in (
                {"type": "http", "url": "http://host/mcp"},
                {"type": "local", "command": "example"},
            ):
                with self.subTest(tools=tools, server=server):
                    config = parse_mcp_config(
                        json.dumps({"mcpServers": {"test": {**server, "tools": tools}}})
                    )
                    self.assertEqual(config["test"]["tools"], tools)

    def test_invalid_configs_are_not_silently_ignored(self) -> None:
        """Reject malformed JSON, server shapes, transports, and credentials."""
        invalid = [
            "{",
            "[]",
            "{}",
            '{"mcpServers":null}',
            '{"mcpServers":[]}',
            '{"mcpServers":{"ha":null}}',
            '{"mcpServers":{"ha":{"transport":[]}}}',
            '{"mcpServers":{"ha":{"type":"unknown"}}}',
            '{"mcpServers":{"ha":{"type":"http","url":"file:///config"}}}',
            '{"mcpServers":{"ha":{"url":"http://host:bad"}}}',
            '{"mcpServers":{"ha":{"url":"http://user:password@host"}}}',
            '{"mcpServers":{"ha":{"url":"http://host","tools":"*"}}}',
            '{"mcpServers":{"ha":{"url":"http://host","tools":[1]}}}',
            '{"mcpServers":{"ha":{"url":"http://host","headers":[]}}}',
            '{"mcpServers":{"ha":{"url":"http://host","headers":{"x":1}}}}',
            '{"mcpServers":{"ha":{"url":"http://host","timeout":true}}}',
            '{"mcpServers":{"ha":{"url":"http://host","timeout":0}}}',
            '{"mcpServers":{"ha":{"url":"http://host","unsupported":true}}}',
            '{"mcpServers":{"ha":{"url":"http://host","type":"sse","transport":"http"}}}',
            '{"mcpServers":{"local":{"type":"local"}}}',
            '{"mcpServers":{"local":{"command":"example","args":"arg"}}}',
            '{"mcpServers":{"local":{"command":"example","env":{"x":1}}}}',
        ]
        for value in invalid:
            with self.subTest(config=value), self.assertRaises(ValueError):
                try:
                    data = json.loads(value)
                except json.JSONDecodeError:
                    parse_mcp_config(value)
                    continue
                # Keep malformed-server coverage independent of missing tools.
                if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
                    for server in data["mcpServers"].values():
                        if isinstance(server, dict):
                            server.setdefault("tools", ["*"])
                parse_mcp_config(json.dumps(data))

    def test_empty_configuration_is_optional(self) -> None:
        """Allow greeting-only sessions without an MCP server."""
        self.assertEqual(parse_mcp_config(""), {})
        self.assertEqual(parse_mcp_config('{"mcpServers":{}}'), {})


class MCPFileTests(IsolatedAsyncioTestCase):
    """Verify that file references really load instead of disabling MCP."""

    async def test_load_file_with_optional_prefix(self) -> None:
        """Read configurations from the Home Assistant filesystem."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.json"
            await asyncio.to_thread(
                path.write_text,
                '{"mcpServers":{"ha":{"type":"sse","url":"http://host/sse","tools":[]}}}',
                encoding="utf-8",
            )
            for value in (str(path), f"@{path}"):
                with self.subTest(path=value):
                    config = await async_load_mcp_config(value)
                    self.assertEqual(config["ha"]["type"], "sse")
                    self.assertEqual(config["ha"]["tools"], [])

    async def test_file_without_tools_is_rejected(self) -> None:
        """File references enforce the same authorization requirement as JSON."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.json"
            await asyncio.to_thread(
                path.write_text,
                '{"mcpServers":{"ha":{"type":"http","url":"http://host/mcp"}}}',
                encoding="utf-8",
            )
            for value in (str(path), f"@{path}"):
                with (
                    self.subTest(path=value),
                    self.assertRaisesRegex(ValueError, "explicit tools list"),
                ):
                    await async_load_mcp_config(value)

    async def test_missing_or_invalid_file_fails(self) -> None:
        """Surface file failures rather than proceeding without tools."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.json"
            with self.assertRaisesRegex(ValueError, "readable inside Home Assistant"):
                await async_load_mcp_config(str(path))
            await asyncio.to_thread(path.write_text, "{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "valid JSON"):
                await async_load_mcp_config(str(path))
