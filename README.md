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
- 🔧 **Configurable Models** - Support for GPT-4o, GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-4.1, GPT-3.5 Turbo, GPT-5, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, Claude Sonnet 4.5, Claude Haiku 4.5, and Claude Opus 4.6
- 💬 **Context Preservation** - Maintains conversation history within sessions via the SDK
- 🐳 **Add-on Support** - Run the Copilot CLI as a Home Assistant add-on instead of installing it locally

## Installation

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

Installing the Copilot CLI inside the Home Assistant Core container can be difficult on Home Assistant OS. The included **GitHub Copilot Bridge** add-on solves this by running the CLI in a dedicated container that the integration connects to over the internal network.

**Current Version**: v3.11.0

**Key Features**:
- 🐳 **Containerized Copilot CLI server** running on port 8000 (internal network only)
- 🔄 **Automatic retry mechanism** with up to 5 restart attempts on failures
- 🔐 **Token-based authentication** via environment variables (no interactive prompts)
- 🏗️ **Multi-architecture support** for amd64 and aarch64 systems
- ✅ **SHA256 checksum verification** for CLI binary integrity
- 🚀 **Auto-start on boot** with configurable GitHub token
- 🛡️ **Hardened authentication** with timeout protection to prevent startup blocking
- 🎯 **Feature detection** for CLI flags to support multiple Copilot CLI versions
- 🧰 **Custom MCP support** via add-on options (inline JSON or config file path)

### Installing the Add-on

1. In Home Assistant, go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** menu (top-right) and choose **Repositories**
3. Add this repository URL: `https://github.com/tserra30/Github-Copilot-SDK-integration`
4. Find **GitHub Copilot Bridge** in the store and click **Install**
5. Go to the add-on's **Configuration** tab and set your GitHub token:
   ```yaml
   github_token: "ghp_yourTokenHere"
   mcp_config: ""
   ```
6. Start the add-on
7. Check the **Log** tab to confirm it started successfully

When `mcp_config` is provided, the add-on passes it to Copilot CLI via
`--additional-mcp-config` so SDK sessions created through the bridge can use MCP tools.

`mcp_config` accepts:
- A JSON object string containing `mcpServers`
- A file path to a JSON config (for example `/config/copilot/mcp.json`)

### MCP Configuration Examples (Bridge Add-on)

**ha-mcp (remote server)**

```yaml
github_token: "ghp_yourTokenHere"
mcp_config: '{"mcpServers":{"ha":{"transport":"streamable-http","url":"http://homeassistant.local:8080/mcp","headers":{"Authorization":"Bearer YOUR_HA_LONG_LIVED_TOKEN"}}}}'
```

**Custom local MCP server**

```yaml
github_token: "ghp_yourTokenHere"
mcp_config: '{"mcpServers":{"mytool":{"type":"local","command":"/usr/local/bin/my-mcp-server","args":[],"tools":["*"]}}}'
```

**Multiple MCP servers**

```yaml
github_token: "ghp_yourTokenHere"
mcp_config: '{"mcpServers":{"ha":{"transport":"streamable-http","url":"http://homeassistant.local:8080/mcp"},"remote-tool":{"transport":"streamable-http","url":"http://remote-mcp-server:3000"}}}'
```

**Use config from file**

```yaml
github_token: "ghp_yourTokenHere"
mcp_config: "/config/copilot/mcp.json"
```

### Finding the Add-on Hostname

The integration needs to know the URL of the running add-on. Within Home Assistant's internal network the add-on is reachable via its hostname, which you can find in the add-on **Info** tab (shown next to "Hostname"). The URL will be:

```
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
   - **GitHub Token** – Your GitHub personal access token with Copilot permissions (optional when using Bridge add-on)
   - **Model** – Select from GPT-4o (default), GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-4.1, GPT-3.5 Turbo, GPT-5, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, Claude Sonnet 4.5, Claude Haiku 4.5, or Claude Opus 4.6
   - **Copilot CLI URL (add-on)** *(optional)* – URL of the GitHub Copilot Bridge add-on (e.g. `http://a1b2c3d4-github-copilot-bridge:8000`). Leave empty to use a locally installed Copilot CLI.

After setup you can adjust additional settings at any time via **Settings** → **Devices & Services** → **GitHub Copilot** → **Configure**:
   - **Response timeout** *(default: 120 s)* – Maximum seconds to wait for a Copilot response. Increase this for reasoning-heavy models such as o1 or o3-mini, or for high-latency connections (range: 10–600 s).

> **Tip for Home Assistant OS users**: Install the GitHub Copilot Bridge add-on (see above) and enter its URL in the "Copilot CLI URL" field. This is the easiest way to get the integration working without manually installing the CLI in the Core container.

> **Note**: When using the Bridge add-on (with CLI URL), you can optionally provide the GitHub Token in the integration setup for reference, but the integration will not pass it to the SDK since the remote server manages its own authentication. The token configured in the add-on itself is what matters for authentication.

> **SDK requirement (all modes)**: The `github-copilot-sdk` package is required whether you connect to a locally installed Copilot CLI or to the Bridge add-on via "Copilot CLI URL" — it is the Python client library the integration uses in both cases. On standard Linux systems (glibc ≥ 2.28), Home Assistant installs it automatically. On Home Assistant OS (glibc < 2.28), the default `0.1.32` wheel is incompatible — see the [SDK Installation](#sdk-installation) section for a workaround. When you leave "Copilot CLI URL" empty (local mode), you **must also** have the Copilot CLI binary installed and authenticated on the same host. The Bridge add-on already includes and manages its own CLI binary.

### GitHub Token & Authentication

#### When Do You Need a GitHub Token?

- **With Bridge add-on**: Configure token in the add-on's `github_token` field only (NOT in the integration)
- **Local CLI mode** (no Bridge): Configure token in the integration's GitHub Token field

#### Creating a GitHub Token

Regardless of which mode you use, you need a valid GitHub Copilot subscription. To create a token:

1. **Verify Copilot subscription**: Ensure you have an active [GitHub Copilot subscription](https://github.com/copilot) (free for verified students, otherwise paid)
2. **Generate a token** from your [GitHub developer settings](https://github.com/settings/tokens)
3. **Keep the token secure** — never share it publicly

#### Token Types & Permissions

**Classic PATs (Personal Access Tokens)**
- Recommended approach for this integration
- Create at: https://github.com/settings/tokens (classic)
- Required scope: `copilot` (enables GitHub Copilot access)
- Recommended scopes: `copilot` + `read:user` (optional, for additional user info)
- If `copilot` scope is unavailable: Ensure your account has an active Copilot subscription and the PAT is created under your personal account (not an organization)
- Note: Very old classic PATs may not have a `copilot` scope option — in this case, create a new token

**Fine-grained PATs**
- More restrictive but supported as an alternative
- Create at: https://github.com/settings/personal-access-tokens/new
- Required permissions:
  - Repository permissions: None required (token can be "All repositories" or specific ones)
  - Account permissions: None specifically named "Copilot", but the account must have an active Copilot subscription
- Note: Fine-grained PATs have less flexibility — if authentication fails with fine-grained, try a classic PAT instead

#### PAT Authentication vs Interactive Login

The Copilot CLI and SDK support two authentication methods:

1. **PAT-based authentication** (what you use in the add-on's `github_token`):
   - Non-interactive (useful for Home Assistant add-ons)
   - Must be a valid token with Copilot permissions
   - Will show "auth probe failed" warning in add-on logs if the token has issues — this warning is **expected** with PATs and does **not** prevent the server from working
   - Check add-on server logs at runtime if authentication fails

2. **Interactive login** (alternative for advanced users):
   - Requires running `copilot auth login` in a shell
   - Most reliable method (avoids PAT permission issues)
   - Only practical for local CLI mode (not for Bridge add-on in Home Assistant OS)
   - Good fallback if PAT-based auth fails

#### Token and Authentication When Using the Bridge Add-on

When you use the Bridge add-on with a CLI URL:
- Configure your GitHub token **only** in the add-on's `github_token` field (Settings → Add-ons → GitHub Copilot Bridge → Configuration)
- The integration does **not** ask for or store a token when using the Bridge add-on
- The bridge server handles all authentication on its own
- If you see "auth probe failed" warning: This is **expected** with token-only setups and does **not** mean the server will fail — the server will still attempt to authenticate at runtime
- If you rotate or revoke the token: Update it **only** in the add-on configuration (not the integration)

#### Token Requirements Checklist

- [ ] GitHub account has an **active Copilot subscription** (free for verified students, paid otherwise)
- [ ] Token created as a **classic PAT** with `copilot` scope (recommended), or a **fine-grained PAT** (fallback)
- [ ] Token is **not expired** and has not been revoked
- [ ] When using Bridge add-on: Token configured in add-on options (not integration)
- [ ] When using local CLI: Token configured in integration (and CLI must be installed and in PATH)
- [ ] If "auth probe failed" appears: Do NOT panic — this is expected with PATs, check server logs for the real error

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

## Troubleshooting

### Bridge add-on MCP configuration

- **`Invalid mcp_config` at startup**: Ensure `mcp_config` is valid JSON containing `mcpServers`, or a valid file path.
- **`file does not exist` error**: If you pass a file path, verify the file exists in the add-on container (for example under `/config`).
- **MCP tools not loaded**: Check add-on logs to confirm your Copilot CLI build supports `--additional-mcp-config`.

### SDK Installation

This integration uses a **patched version** of `github-copilot-sdk` (version `0.1.22+ha`) that is automatically installed from this repository's `wheels/` directory. This patched wheel:

- ✅ Is a universal `py3-none-any` wheel compatible with **all platforms** including Home Assistant OS
- ✅ Supports **protocol v3** (required for Copilot CLI v1.0.13)
- ✅ Maintains **backward compatibility** with protocol v2
- ✅ Works on systems with **any glibc version** (no manylinux requirements)

**Why a patched wheel?**
- Official SDK versions 0.1.23+ only ship `manylinux_2_28` wheels requiring glibc ≥ 2.28
- Home Assistant OS has glibc < 2.28 and cannot install these wheels
- SDK 0.1.22 (last version with universal wheels) only supports protocol v2
- Our patched `0.1.22+ha` combines the best of both: universal wheels + protocol v3 support

**Wheel Details:**
- **Source**: Built from SDK 0.1.22 with protocol v3 patches (see `wheels/README.md`)
- **Build Process**: Automated via `.github/workflows/build-sdk.yml`
- **Installation**: Automatic from `manifest.json` using a pinned, immutable commit SHA URL with sha256 verification
- **Reproducibility**: The URL is pinned to commit `fd973cc65828d677d69e8f2406a69aa140858cd8` — use the same pinned URL for any manual installs rather than a mutable `raw/main/...` URL

The SDK is required in **both** modes (bridge add-on and local CLI) as it is the Python client library used by the integration.

> **Note**: The Bridge add-on eliminates the need to install the **Copilot CLI binary** locally, but the Python `github-copilot-sdk` package is still required by the integration to communicate with that server.

### "Unable to connect to Copilot CLI" Error

This error means the GitHub Copilot CLI is not reachable. There are two ways to fix it:

**Option A – Use the GitHub Copilot Bridge add-on (recommended for Home Assistant OS)**

1. Install the add-on as described in the [GitHub Copilot Bridge Add-on](#github-copilot-bridge-add-on-recommended-for-home-assistant-os) section
2. Make sure the add-on is running and the Log tab shows no errors
3. Enter the add-on URL (e.g. `http://a1b2c3d4-github-copilot-bridge:8000`) in the **Copilot CLI URL** field during integration setup

**Option B – Install the CLI locally inside the Core container**

1. **Install the Copilot CLI**: Visit https://docs.github.com/copilot/cli for installation instructions
2. **Ensure CLI is in PATH**: Run `which copilot` or `copilot --version` to verify installation (or set `COPILOT_CLI_PATH` to the binary)
3. **Authenticate the CLI**: Run `copilot auth login` to authenticate with your GitHub account
4. **Check Copilot subscription**: Ensure you have an active GitHub Copilot subscription

#### Home Assistant OS specifics

> **Easiest approach**: Install the **GitHub Copilot Bridge** add-on from this repository (see [above](#github-copilot-bridge-add-on-recommended-for-home-assistant-os)). The steps below are only needed if you prefer to install the CLI manually.

The Copilot CLI must be available **inside the Home Assistant Core container**, not only the SSH/Terminal add-on. Typical steps:

1. Open the Advanced SSH & Web Terminal add-on and enter the Core container:
   ```bash
   docker exec -it homeassistant /bin/sh   # or /bin/bash if available
   ```
2. Install the Copilot CLI **inside this container** following the official docs: https://docs.github.com/copilot/cli. You can place the `copilot` binary at `/config/copilot` or `/config/bin/copilot` to persist across updates (these paths are automatically discovered by the integration), or in a standard location like `/usr/local/bin/copilot`. Example for Alpine/amd64:
   ```bash
   apk add --no-cache curl ca-certificates
   # Option 1: Place at /config/bin/copilot (persists across updates, automatically discovered)
   mkdir -p /config/bin
   curl -L https://github.com/github/copilot-cli/releases/latest/download/copilot-linux-amd64 -o /config/bin/copilot
   chmod +x /config/bin/copilot
   /config/bin/copilot --version

   # Option 2: Place at /usr/local/bin/copilot (requires reinstall on updates)
   curl -L https://github.com/github/copilot-cli/releases/latest/download/copilot-linux-amd64 -o /usr/local/bin/copilot
   chmod +x /usr/local/bin/copilot
   copilot --version
   ```
   For Debian/Ubuntu containers, adapt by installing dependencies with `apt-get` and downloading the matching `copilot` binary for your architecture.
3. Authenticate the Copilot CLI in that same shell:
   ```bash
   # If you installed in /config/bin:
   /config/bin/copilot auth login

   # If you installed in a PATH location like /usr/local/bin:
   copilot auth login
   ```
4. Persist authentication by moving the Copilot CLI config into `/config` and pointing the CLI to it:
   ```bash
   mkdir -p /config/.gh_config
   mv /root/.config/gh/* /config/.gh_config/ 2>/dev/null || true
   export GH_CONFIG_DIR=/config/.gh_config
   ```
5. **Optional**: If you used Option 2 (installing in `/usr/local/bin`), you can make the install persistent across restarts with a shell command + automation (adapt the install command for your base OS/architecture):
   ```yaml
   # configuration.yaml (automation can live in automations.yaml if you split config)
   shell_command:
     install_copilot_cli: "apk add --no-cache curl ca-certificates && curl -L https://github.com/github/copilot-cli/releases/latest/download/copilot-linux-amd64 -o /usr/local/bin/copilot && chmod +x /usr/local/bin/copilot"

   automation:
     - alias: "Ensure Copilot CLI on boot"
       id: ensure_copilot_cli
       trigger:
         - platform: homeassistant
           event: start
       action:
         - service: shell_command.install_copilot_cli
   ```
   **Note**: If you used Option 1 (`/config/bin`), this automation is not needed as the binary already persists across updates.

   If the CLI binary lives outside PATH and outside the auto-discovered locations (`/config/copilot`, `/config/bin/copilot`, `~/.local/bin/copilot`, `/usr/local/bin/copilot`, `/usr/bin/copilot`), set `COPILOT_CLI_PATH` to its location in your environment.

### Authentication Errors

#### "Authentication failed" or "GitHub Copilot CLI is not authenticated"

This error means the Copilot CLI (or SDK via the CLI) cannot authenticate with your GitHub account.

**If using the Bridge add-on:**

1. **Check that the GitHub token is configured in the add-on**:
   - Go to Settings → Add-ons → GitHub Copilot Bridge → Configuration
   - Ensure `github_token` is set (not empty)
   - Do **not** add a token to the integration config when using the Bridge add-on

2. **Verify the token has Copilot permissions**:
   - Check [GitHub Token Settings](https://github.com/settings/tokens) for your token
   - For classic PATs: Ensure the `copilot` scope is enabled
   - For fine-grained PATs: Ensure your GitHub account has an active Copilot subscription
   - If `copilot` scope is missing from classic PATs: Your account or the token may be too old; create a new classic PAT

3. **Check the add-on logs for the real error**:
   - Go to Settings → Add-ons → GitHub Copilot Bridge → Logs
   - Look for error messages after "Starting GitHub Copilot CLI server"
   - "auth probe failed" warning is **expected** with PATs — keep reading the logs for the actual error
   - Common runtime errors:
     - "Invalid credentials": Token is invalid or lacks Copilot permissions
     - "Subscription required": Account does not have an active Copilot subscription
     - "rate limit exceeded": Too many authentication attempts (wait 10-15 minutes before retrying)

4. **Restart the add-on and integration**:
   - Restart the Bridge add-on from Settings → Add-ons
   - Then restart Home Assistant (or just reload the GitHub Copilot integration)
   - Check the add-on logs again

5. **Try a different token type**:
   - If using a fine-grained PAT: Create a classic PAT with the `copilot` scope instead
   - If the token is old: Generate a new token from https://github.com/settings/tokens

**If using local Copilot CLI (no Bridge):**

- Verify your GitHub token is configured in the integration setup
- Ensure the Copilot CLI is installed and authenticated: Run `copilot auth login` in the Core container
- Check that your CLI version is compatible with the SDK (see SDK Installation section)
- Try re-running `copilot auth login` for interactive authentication (more reliable than PATs)

#### About the "auth probe failed" Warning

When using the Bridge add-on with a PAT token, you may see this warning in the add-on logs:
```
Copilot CLI auth probe failed. This can be expected with token-only setups. Proceeding to start the server...
```

**This warning is expected and normal.** It does **not** mean authentication will fail at runtime. The warning appears because:
- The authentication probe is a quick check that works well with interactive login but has limitations with token-only setups
- The actual authentication happens later when the Copilot CLI server starts
- If the token is valid, the server will authenticate successfully despite this warning

**If you see this warning BUT the server works**: Your setup is correct; you can ignore the warning.

**If you see this warning AND the server fails to work**: Check the add-on logs for the actual error message (usually appears after "Starting GitHub Copilot CLI server"). The real error will tell you what's wrong (invalid token, missing subscription, etc.).

### Connection Issues

- Check your internet connectivity
- Verify the Copilot CLI is running: `copilot --version`
- Check Home Assistant logs for detailed error messages

### Slow Responses or Timeout Errors

If you see a `TimeoutError: Timeout after Xs waiting for session.idle` error, the integration waited longer than the configured limit before Copilot replied.

- **Increase the response timeout**: Go to **Settings** → **Devices & Services** → **GitHub Copilot** → **Configure** and raise the **Response timeout** (default 120 s, up to 600 s). Reasoning models such as o1 and o3-mini can take significantly longer than GPT-4o.
- Try using a faster model (e.g., GPT-3.5 Turbo or GPT-4o-mini)
- Check your network latency
- Reduce concurrent requests

For more help, [open an issue][issues].

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the GNU GPLv3 - see the [LICENSE](LICENSE) file for details.
Some source code was originally licensed under the MIT license.

### GitHub Copilot SDK License

This integration depends on the GitHub Copilot SDK, which is licensed under the MIT License:

```
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
```
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
