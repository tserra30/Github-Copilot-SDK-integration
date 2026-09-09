# GitHub Copilot Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

_Integration to bring GitHub Copilot AI capabilities to Home Assistant using the GitHub Copilot SDK._

**This integration provides a conversation agent powered by the GitHub Copilot SDK and Copilot CLI, enabling voice assistants and AI-powered tasks similar to OpenAI, Claude, and Gemini integrations.**

## Features

- 🤖 **Conversation Agent** - Use GitHub Copilot as an AI conversation agent
- 🎤 **Voice Assistant Support** - Works with Home Assistant's voice pipeline
- 🔧 **Configurable Models** - Default to `auto`, or select an available model through the integration's options
- 💬 **Context Preservation** - Maintains conversation history within sessions via the SDK
- 🐳 **Add-on Support** - Run the Copilot CLI as a Home Assistant add-on instead of installing it locally
- 🧰 **MCP Tools** - Connect to Home Assistant's built-in MCP server or other explicitly authorized MCP servers

## Installation

Requires Home Assistant 2025.2.4 or later. Use a current stable Home Assistant release for the built-in MCP server setup below.

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the "+" button
4. Search for "GitHub Copilot"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/github_copilot` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## GitHub Copilot Bridge Add-on (Recommended for Home Assistant OS)

The **GitHub Copilot Bridge** add-on runs the CLI in a dedicated container that the integration connects to over the internal network. Bridge mode needs no CLI binary or runtime download inside Home Assistant Core.

**Current Version**: v3.12.0 (Copilot CLI v1.0.83)

**Key Features**:
- 🐳 **Containerized Copilot CLI server** running on port 8000 (internal network only)
- 🔄 **Automatic retry mechanism** with up to 5 restart attempts on failures
- 🔐 **Token-based authentication** via environment variables (no interactive prompts)
- 🏗️ **Multi-architecture support** for amd64 and aarch64 systems
- ✅ **SHA256 checksum verification** for CLI binary integrity
- 🚀 **Auto-start on boot** with configurable GitHub token
- 🛡️ **Hardened authentication** with timeout protection to prevent startup blocking
- 🎯 **Feature detection** for CLI flags to support multiple Copilot CLI versions
- 🧰 **Custom MCP support** via integration settings or add-on options for other clients

### Installing the Add-on

1. In Home Assistant, go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** menu (top-right) and choose **Repositories**
3. Add this repository URL: `https://github.com/tserra30/Github-Copilot-SDK-integration`
4. Find **GitHub Copilot Bridge** in the store and click **Install**
5. Go to the add-on's **Configuration** tab and set your GitHub fine-grained personal access token:
   ```yaml
   github_token: "github_pat_REPLACE_WITH_YOUR_TOKEN"
   mcp_config: ""
   ```
6. Start the add-on
7. Check the **Log** tab to confirm it started successfully

**For this integration, put MCP configuration in the integration's MCP field, even when using the bridge.** Add-on `mcp_config` alone does not authorize tools for this integration. See [MCP configuration](#mcp-configuration).

The add-on's optional `mcp_config` remains available for other bridge clients. It accepts an inline JSON object containing `mcpServers` or a JSON file path readable **inside the add-on container**, and is passed to the CLI via `--additional-mcp-config`. Leave it empty if you only use the integration's MCP configuration.

### Finding the Add-on Hostname

The integration needs the URL of the running add-on. Find its hostname in the add-on's **Info** tab and enter:

```text
http://<hostname>:8000
```

For example: `http://a1b2c3d4-github-copilot-bridge:8000`

> **Note**: Home Assistant generates the hostname from the add-on slug by replacing all underscores (`_`) with hyphens (`-`). Always use hyphens in the hostname — using the raw slug with underscores will cause DNS resolution to fail.

## Configuration

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **GitHub Copilot**
4. Fill in the configuration:
   - **GitHub Token** – Your GitHub fine-grained personal access token with Copilot permissions (optional when using the bridge)
   - **Model** – Leave at `auto` (recommended for new installations), or enter a supported model ID. Setup also accepts custom IDs.
   - **Copilot CLI URL (add-on)** *(optional)* – URL of the bridge (e.g. `http://a1b2c3d4-github-copilot-bridge:8000`). Leave empty for local mode; the SDK can download its matching CLI runtime automatically.
   - **MCP configuration** *(optional)* – Inline JSON containing `mcpServers`, or a JSON file path readable by Home Assistant Core. See [MCP configuration](#mcp-configuration).

After setup, adjust settings through **Settings** → **Devices & Services** → **GitHub Copilot** → **Configure**. **Response timeout** defaults to 120 seconds (range: 10–600 seconds); increase it for reasoning-heavy models or high-latency connections.

**Upgrading an existing installation?** Saved model selections are preserved, not silently replaced with `auto`. Open **Configure** to fetch the runtime's available model IDs and select a supported model. An older saved ID can become unavailable even if it worked before the SDK/CLI upgrade.

> **Tip for Home Assistant OS users**: Install the bridge and enter its URL in the "Copilot CLI URL" field. No manual CLI installation in the Core container is needed.

> **Note**: With a CLI URL, the integration does not pass a GitHub token to the SDK. Configure GitHub authentication in the bridge itself.

### GitHub Token & Authentication

1. Ensure your GitHub account has active [Copilot access](https://github.com/copilot), subject to your plan and organization policies.
2. Create a **fine-grained personal access token** at [GitHub token settings](https://github.com/settings/personal-access-tokens/new).
3. Grant **Account permissions → Copilot Requests → Read and write**. Repository permissions are not required for this integration.
4. For **bridge mode**, put the token in the add-on's `github_token` field. The integration's GitHub Token field is optional and is not passed to the SDK.
5. For **local mode**, put the token in the integration's GitHub Token field (required).

**Classic PATs (`ghp_...`) are not supported by the current SDK authentication guidance.** Do not look for a classic `copilot` scope or switch to a classic PAT to fix authentication.

Keep tokens private and rotate them when needed. Update a rotated token where it is used: in the bridge configuration for remote mode, or in the integration for local mode. The Home Assistant token used for MCP below is a **different credential**.

### MCP Configuration

Enter MCP settings in the **GitHub Copilot integration's MCP configuration field**, during setup or through **Configure**. This field accepts:

- Inline JSON with a top-level `mcpServers` object, as shown below.
- A JSON file path, such as `/config/copilot/mcp.json` or `@/config/copilot/mcp.json`. The file must be readable by **Home Assistant Core**, even in bridge mode; file loading runs off the event loop.

MCP configuration is validated during **both setup and options changes**. Files are loaded off the event loop; invalid JSON, unreadable files, and invalid server definitions produce configuration errors rather than being silently accepted or disabling MCP. Remote server definitions use `type: "http"` or `type: "sse"`, a `url`, and a `tools` list; optional `headers` provide authentication. Use `tools: ["*"]` to authorize every tool on a trusted server, or an explicit list of that server's tool names for narrower access. Legacy `transport: "streamable-http"` and local working-directory `cwd` aliases are normalized for compatibility.

Configured tool allowlists are **authorization**, not just discovery: allowed MCP tool calls can execute without an interactive approval prompt. Only authorize servers and tools you trust. Built-in CLI tools are disabled, and unknown or unconfigured MCP servers/tools are denied. Add-on `mcp_config` alone does not grant this authorization.

#### Home Assistant's Built-in MCP Server

No external MCP server or proxy is needed:

1. Use a current stable Home Assistant release with the [Model Context Protocol Server integration](https://www.home-assistant.io/integrations/mcp_server/). The older 2024 development baseline does not include it.
2. Go to **Settings → Devices & services → Add integration → Model Context Protocol Server**.
3. Enable its **Assist API**, and expose a safe test entity to Assist under **Settings → Voice assistants → Expose**. For example, use an input boolean helper rather than a lock or other safety-sensitive device.
4. Create a **Home Assistant long-lived access token** from your Home Assistant profile's security settings. This is separate from your GitHub fine-grained PAT.
5. Paste the following JSON into the **GitHub Copilot integration's MCP configuration field**, replacing the Home Assistant token placeholder:

```json
{
  "mcpServers": {
    "homeassistant": {
      "type": "http",
      "url": "http://homeassistant:8123/api/mcp",
      "tools": ["*"],
      "headers": {
        "Authorization": "Bearer REPLACE_WITH_HOME_ASSISTANT_LONG_LIVED_TOKEN"
      }
    }
  }
}
```

`http://homeassistant:8123/api/mcp` is the endpoint reachable from the bridge on Home Assistant's internal network. For other deployments, use an address reachable from the **Copilot CLI runtime**, not just from your browser. Keep plain HTTP on a trusted internal network; use HTTPS for untrusted networks.

Ask the conversation agent to turn the exposed test helper on, then off. Verify its actual state in Home Assistant after each request; a natural-language success message alone does not prove a tool executed. Protect MCP configuration files and headers as credentials, and never include tokens in issue reports or logs.

## Usage

### As a Conversation Agent

Once configured, you can:

1. Select GitHub Copilot as a conversation agent in voice assistants
2. Use it in automations via the `conversation.process` service
3. Chat with it through the Home Assistant UI

### Example Automation

```yaml
automation:
  - alias: "Morning briefing with Copilot"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: conversation.process
        data:
          text: "Good morning! What should I know today?"
          agent_id: conversation.github_copilot
```

## Documentation

For detailed setup and usage guidance, use this README. For contributing and development details, see [CONTRIBUTING.md](CONTRIBUTING.md).

The upgrade validation environment is **official Home Assistant Container 2026.9.1**, with Docker Engine in Ubuntu WSL2 and the built bridge image running as an external CLI server. This container has no Supervisor: that setup cannot validate the full add-on lifecycle and is not Home Assistant OS validation. See the contribution guide for checks and how to report actual results.

## Troubleshooting

### "Model not available"

An older model ID, such as `gpt-4.1`, can be rejected by the new runtime even if a previous installation could use it. Open **Settings → Devices & Services → GitHub Copilot → Configure** and choose a currently offered supported model. New installations default to `auto`; existing saved selections are not automatically migrated.

### MCP Configuration and Tool Calls

- **Invalid configuration**: Check that the JSON contains `mcpServers` and valid server definitions. Prefer canonical `type: "http"` or `"sse"` for remote servers and include `tools`.
- **File not found or unreadable**: A file used in the integration must exist in Home Assistant Core's filesystem. A file used only in the add-on's `mcp_config` must exist inside that separate add-on container.
- **Tools unavailable or denied**: Put the server and its allowed tools in the **integration's MCP field**, not just the add-on options. For explicit allowlists, use the exact tool names exposed by the server.
- **Home Assistant MCP authentication fails**: Use a Home Assistant long-lived access token with the `Bearer` prefix, not a GitHub PAT.
- **Entity cannot be controlled**: Enable the MCP server's Assist API and expose the test entity to Assist. Verify its real state, not just the assistant's response.
- **Connection fails**: Confirm the MCP URL is reachable from the CLI runtime. From the bridge, use `http://homeassistant:8123/api/mcp`; `localhost` would refer to the bridge itself.

### SDK Installation

Home Assistant automatically installs upstream **`github-copilot-sdk==1.0.13`** from PyPI using the integration manifest. Its universal **`py3-none-any`** wheel supports Home Assistant's Python environment without a bundled or patched wheel. Home Assistant Core's container uses **Alpine/musl**, not an older glibc.

The Python SDK is required in **both** modes:

- **Local mode** (no CLI URL): When no installed or explicit CLI executable is available, the SDK automatically downloads and verifies a checksummed matching runtime. SDK 1.0.13 pins CLI **1.0.83**, with musl and glibc builds for amd64/arm64. Allow outbound access for the first download and ensure its cache location is writable.
- **Remote bridge mode**: The SDK connects to the bridge and neither needs a local CLI executable nor downloads one. Update the bridge along with the integration to keep its CLI compatible.

If an old manual CLI installation or `COPILOT_CLI_PATH` override is selected, update it to a compatible version or remove the stale override so the SDK can manage its runtime. Do not reinstall old patched wheels or use boot-time binary-download automations.

### "Unable to connect to Copilot CLI" Error

**Bridge mode**:

1. Confirm the add-on is running and check its logs.
2. Check the integration's CLI URL and hostname, including hyphens rather than underscores.
3. Check that GitHub authentication is configured in the add-on.

**Local mode**:

1. Check Home Assistant logs for runtime download, permissions, or startup errors.
2. Confirm outbound connectivity and a writable SDK runtime cache.
3. Check for a stale manually installed CLI or `COPILOT_CLI_PATH` override.
4. Confirm the integration has a valid fine-grained GitHub PAT.

Installing a CLI only in the SSH/Terminal add-on does not make it available inside Home Assistant Core.

### Authentication Errors

- Check that the fine-grained GitHub PAT is not expired or revoked, has **Account permissions → Copilot Requests → Read and write**, and belongs to an account with Copilot access.
- In bridge mode, update the add-on's `github_token` and restart the bridge; changing the integration token does not change remote authentication.
- In local mode, update the integration token.
- Check runtime logs for invalid credentials, plan restrictions, or rate limits. Respect any reported retry delay.

An **"auth probe failed"** warning in bridge logs is inconclusive. Token-only setups can still work, but do not assume the warning is harmless: check subsequent runtime logs and a real conversation request.

### Slow Responses or Timeout Errors

- **Increase the response timeout**: Go to **Settings** → **Devices & Services** → **GitHub Copilot** → **Configure** (default 120 seconds, up to 600 seconds).
- Try a faster model and check network latency.
- Check MCP server availability if a response requires tools.
- Reduce concurrent requests.

For more help, [open an issue][issues]. Redact tokens and authorization headers from diagnostic output.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the GNU GPLv3 - see the [LICENSE](LICENSE) file for details.
Some source code was originally licensed under the MIT license.

### GitHub Copilot SDK License

This integration depends on the GitHub Copilot SDK, which is licensed under the MIT License:

```text
MIT License

Copyright GitHub, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Acknowledgments

- Built on Home Assistant's conversation framework
- Based on the integration blueprint by [@ludeeus](https://github.com/ludeeus)

---

**Note**: This integration is not officially affiliated with GitHub or Microsoft.
## Original MIT license from integration blueprint by [@ludeeus](https://github.com/ludeeus)
```text
MIT License

Copyright (c) 2019 - 2025  Joakim Sørensen @ludeeus

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
[commits-shield]: https://img.shields.io/github/commit-activity/y/tserra30/Github-Copilot-SDK-integration.svg?style=for-the-badge
[commits]: https://github.com/tserra30/Github-Copilot-SDK-integration/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/tserra30/Github-Copilot-SDK-integration.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/tserra30/Github-Copilot-SDK-integration.svg?style=for-the-badge
[releases]: https://github.com/tserra30/Github-Copilot-SDK-integration/releases
[issues]: https://github.com/tserra30/Github-Copilot-SDK-integration/issues
