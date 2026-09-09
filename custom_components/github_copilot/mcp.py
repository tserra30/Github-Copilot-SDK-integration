"""Validate MCP configuration shared by setup and SDK sessions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from copilot import MCPServerConfig


def is_mcp_config_path(value: str) -> bool:
    """Return whether a configuration value is a file reference."""
    value = value.strip()
    return value.startswith("@") or (
        not value.startswith(("{", "["))
        and any(separator in value for separator in ("/", "\\"))
    )


def _string_mapping(value: Any) -> bool:
    """Check string-valued HTTP headers or process environment variables."""
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


async def async_load_mcp_config(value: str) -> dict[str, MCPServerConfig]:
    """Read HA-local JSON files without blocking the Home Assistant event loop."""
    value = value.strip()
    if is_mcp_config_path(value):
        try:
            value = await asyncio.to_thread(_read_mcp_config, value.removeprefix("@"))
        except (OSError, UnicodeError, ValueError, RuntimeError) as exception:
            msg = "MCP configuration file must be readable inside Home Assistant."
            raise ValueError(msg) from exception
    return parse_mcp_config(value)


def _read_mcp_config(path: str) -> str:
    """Resolve and read a configuration file in an executor thread."""
    return Path(path).expanduser().read_text(encoding="utf-8")


def parse_mcp_config(value: str) -> dict[str, MCPServerConfig]:
    """Parse inline JSON, rejecting invalid servers without logging secrets."""
    if not value.strip():
        return {}
    try:
        data = json.loads(value)
    except (json.JSONDecodeError, RecursionError) as exception:
        msg = "MCP configuration must be valid JSON."
        raise ValueError(msg) from exception
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers"), dict):
        msg = "MCP configuration must contain an object-valued 'mcpServers'."
        raise ValueError(msg)  # noqa: TRY004 - Invalid JSON value, not argument type.

    servers: dict[str, MCPServerConfig] = {}
    for name, raw in data["mcpServers"].items():
        if not isinstance(name, str) or not name.strip() or not isinstance(raw, dict):
            msg = (
                "Each MCP server must have a non-empty name "
                "and an object configuration."
            )
            raise ValueError(msg)
        server = dict(raw)
        transport = server.pop("transport", None)
        if transport is not None:
            if not isinstance(transport, str):
                msg = "MCP transport must be a string."
                raise ValueError(msg)
            transport = {"streamable-http": "http"}.get(transport, transport)
            if "type" in server and server["type"] != transport:
                msg = "MCP server type and transport must agree."
                raise ValueError(msg)
            server["type"] = transport
        server_type = server.get("type", "http" if "url" in server else "local")
        tools = server.get("tools", ["*"])
        if not isinstance(tools, list) or not all(
            isinstance(tool, str) and tool for tool in tools
        ):
            msg = "MCP tools must be a list of non-empty tool names or ['*']."
            raise ValueError(msg)

        config: MCPServerConfig
        if server_type in ("http", "sse"):
            url = server.get("url")
            try:
                parsed = urlparse(url) if isinstance(url, str) else None
                valid_url = (
                    parsed is not None
                    and parsed.scheme in ("http", "https")
                    and bool(parsed.hostname)
                    and (parsed.port is None or parsed.port > 0)
                    and parsed.username is None
                    and parsed.password is None
                )
            except ValueError:
                valid_url = False
            if not valid_url:
                msg = "Remote MCP servers require an HTTP(S) URL without credentials."
                raise ValueError(msg)
            config = {"type": server_type, "url": url, "tools": tools}
            if "headers" in server:
                if not _string_mapping(server["headers"]):
                    msg = "MCP headers must be an object containing string values."
                    raise ValueError(msg)
                config["headers"] = server["headers"]
            allowed = {"type", "url", "tools", "headers", "timeout"}
        elif server_type in ("local", "stdio"):
            command = server.get("command")
            args = server.get("args", [])
            if not isinstance(command, str) or not command.strip():
                msg = "Local MCP servers require a command."
                raise ValueError(msg)
            if not isinstance(args, list) or not all(
                isinstance(arg, str) for arg in args
            ):
                msg = "Local MCP server arguments must be a list of strings."
                raise ValueError(msg)
            config = {
                "type": server_type,
                "command": command,
                "args": args,
                "tools": tools,
            }
            if "env" in server:
                if not _string_mapping(server["env"]):
                    msg = "MCP environment variables must contain string values."
                    raise ValueError(msg)
                config["env"] = server["env"]
            directory = server.get("working_directory", server.get("cwd"))
            if directory is not None:
                if not isinstance(directory, str):
                    msg = "MCP working_directory must be a string."
                    raise ValueError(msg)
                config["working_directory"] = directory
            allowed = {
                "type",
                "command",
                "args",
                "tools",
                "env",
                "working_directory",
                "cwd",
                "timeout",
            }
        else:
            msg = "MCP server type must be http, sse, local, or stdio."
            raise ValueError(msg)

        if set(server) - allowed:
            msg = "MCP server configuration contains unsupported fields."
            raise ValueError(msg)
        if "timeout" in server:
            timeout = server["timeout"]
            if type(timeout) is not int or timeout <= 0:
                msg = "MCP timeout must be a positive integer in milliseconds."
                raise ValueError(msg)
            config["timeout"] = timeout
        servers[name] = config
    return servers
