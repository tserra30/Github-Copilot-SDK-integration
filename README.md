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
- 🔧 **Configurable Models** - Support for GPT-4o, GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, and Claude 3.7 Sonnet
- 💬 **Context Preservation** - Maintains conversation history within sessions via the SDK
- ⚠️ **Copilot CLI Required** - The GitHub Copilot SDK uses the Copilot CLI for authentication and runtime

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

## Configuration

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **GitHub Copilot**
4. Enter your GitHub token for Copilot SDK authentication
5. Configure optional settings:
   - **Model**: Select from GPT-4o (default), GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, or Claude 3.7 Sonnet

### Getting a GitHub Token

To use this integration, you need a GitHub personal access token that can authenticate the Copilot SDK:
1. Ensure you have an active GitHub Copilot subscription
2. Install the GitHub Copilot CLI and sign in, or provide a PAT token for the SDK.
3. Generate a PAT token from your GitHub developer settings.
4. Make sure to add the necessary permissions to the token. (e.g., Copilot requests)
5. Keep the token secure

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

For detailed documentation, see [agents.md](agents.md)

## Troubleshooting

### "Unable to connect to Copilot CLI" Error

This error indicates the GitHub Copilot CLI is not properly installed or configured:

1. **Install the Copilot CLI**: Visit https://docs.github.com/copilot/cli for installation instructions
2. **Ensure CLI is in PATH**: Run `which copilot` or `copilot --version` to verify installation (or set `COPILOT_CLI_PATH` to the binary)
3. **Authenticate the CLI**: Run `copilot auth login` to authenticate with your GitHub account
4. **Check Copilot subscription**: Ensure you have an active GitHub Copilot subscription

#### Home Assistant OS specifics

The Copilot CLI must be available **inside the Home Assistant Core container**, not only the SSH/Terminal add-on. Typical steps:

1. Open the Advanced SSH & Web Terminal add-on and enter the Core container:
   ```bash
   docker exec -it homeassistant /bin/sh   # or /bin/bash if available
   ```
2. Install the Copilot CLI **inside this container** following the official docs: https://docs.github.com/copilot/cli. Use a package manager appropriate for your base OS (e.g., `apk` on Alpine, `apt` on Debian/Ubuntu) to install prerequisites, then place the `copilot` binary in PATH. Example for Alpine/amd64:
   ```bash
   apk add --no-cache curl ca-certificates
   curl -L https://github.com/github/copilot-cli/releases/latest/download/copilot-linux-amd64 -o /usr/local/bin/copilot
   chmod +x /usr/local/bin/copilot
   copilot --version
   ```
   For Debian/Ubuntu containers, adapt by installing dependencies with `apt-get` and downloading the matching `copilot` binary for your architecture.
3. Authenticate the Copilot CLI in that same shell:
   ```bash
   copilot auth login
   ```
4. Persist authentication by moving the Copilot CLI config into `/config` and pointing the CLI to it:
   ```bash
   mkdir -p /config/.gh_config
   mv /root/.config/gh/* /config/.gh_config/ 2>/dev/null || true
   export GH_CONFIG_DIR=/config/.gh_config
   ```
5. Make the install persistent across restarts with a shell command + automation (adapt the install command for your base OS/architecture):
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
   If the CLI binary lives outside PATH, set `COPILOT_CLI_PATH` to its location in your environment.

### Authentication Errors

- Verify your GitHub token is valid and has Copilot permissions
- Ensure your GitHub Copilot subscription is active
- Try regenerating your personal access token

### Connection Issues

- Check your internet connectivity
- Verify the Copilot CLI is running: `copilot --version`
- Check Home Assistant logs for detailed error messages

### Slow Responses

- Try using a faster model (e.g., GPT-3.5 Turbo or GPT-4o-mini)
- Check your network latency
- Reduce concurrent requests

For more help, see the [agents.md](agents.md) documentation or [open an issue][issues].

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
