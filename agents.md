# GitHub Copilot Home Assistant Integration - Agents Documentation

## Overview

This integration adds GitHub Copilot AI capabilities to Home Assistant using the GitHub Copilot SDK, enabling voice assistants and other AI-powered tasks similar to OpenAI, Claude, and Gemini integrations.

## Features

- **Conversation Agent**: Use GitHub Copilot as a conversation agent in Home Assistant
- **Voice Assistant Support**: Compatible with Home Assistant's voice assistant pipeline
- **Configurable Models**: Support for multiple GPT models (GPT-4o, GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, Claude 3.7 Sonnet)
- **Context Preservation**: Maintains conversation history within sessions via the SDK
- **Copilot CLI Runtime**: Uses the GitHub Copilot CLI managed by the SDK

## Installation

### Via HACS (Home Assistant Community Store)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the "+" button
4. Search for "GitHub Copilot"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/github_copilot` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### Through the UI

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **GitHub Copilot**
4. Enter your configuration:
    - **API Token**: Your GitHub token for Copilot SDK authentication
- **Model**: Select the AI model (default: GPT-4o)

### Getting a GitHub Token

To use this integration, you need a GitHub token to authenticate the Copilot SDK:

1. Ensure you have an active GitHub Copilot subscription
2. Install the GitHub Copilot CLI and sign in, or provide a PAT token to the SDK
3. Visit GitHub's API token settings
4. Generate a new token with appropriate permissions
5. Copy and save the token securely

**Note**: Keep your GitHub token secure and never share it publicly.

## Usage

### As a Conversation Agent

Once configured, GitHub Copilot will appear as a conversation agent in Home Assistant:

1. Go to **Settings** → **Voice assistants**
2. Create or edit an assistant
3. Select **GitHub Copilot** as the conversation agent
4. Save your changes

You can now use GitHub Copilot with:
- Voice assistants (Assist)
- Chat interface
- Automations using the conversation service

### Example Service Calls

#### Basic Conversation

```yaml
service: conversation.process
data:
  text: "What's the weather like today?"
  agent_id: conversation.github_copilot
```

#### In Automations

```yaml
automation:
  - alias: "Ask Copilot about energy usage"
    trigger:
      - platform: time
        at: "18:00:00"
    action:
      - service: conversation.process
        data:
          text: "Summarize my energy usage today"
          agent_id: conversation.github_copilot
```

### Voice Assistant Integration

GitHub Copilot can be used with Home Assistant's voice pipeline:

1. Configure a voice assistant (Assist)
2. Select GitHub Copilot as the conversation agent
3. Use wake word + voice commands
4. GitHub Copilot will process and respond to your requests

## Advanced Configuration

### Model Selection

Different models offer various capabilities:

- **GPT-4o**: Default, balanced speed and capability
- **GPT-4o-mini**: Faster responses, smaller model
- **GPT-4**: Most capable, best reasoning and instruction following
- **GPT-4 Turbo**: Faster responses, good balance of speed and capability
- **GPT-3.5 Turbo**: Fastest, suitable for simple conversations
- **o3-mini**: Reasoning-focused model
- **o1 / o1-mini**: Reasoning models with extended context
- **Claude 3.5 Sonnet / Claude 3.7 Sonnet**: Anthropic models supported via Copilot

## Troubleshooting

### Copilot CLI Not Found

**Issue**: "Unable to connect to Copilot CLI" or "GitHub Copilot CLI not found"

**Solutions**:
1. Install the GitHub Copilot CLI from https://docs.github.com/copilot/cli
2. Verify installation by running `copilot --version` in a terminal (or set `COPILOT_CLI_PATH` to the binary)
3. Ensure the CLI is in your PATH or in an auto-discovered location (`~/.local/bin/copilot`, `/usr/local/bin/copilot`, `/usr/bin/copilot`, `/config/copilot`, `/config/bin/copilot`)
4. Authenticate the CLI by running `copilot auth login`
5. Check that your GitHub account has an active Copilot subscription

**Home Assistant OS container tips**

- The CLI must be installed **inside** the `homeassistant` container. From the Advanced SSH add-on:
  ```bash
  docker exec -it homeassistant /bin/sh   # or /bin/bash if available
  ```
- Install the Copilot CLI inside this container following https://docs.github.com/copilot/cli. You can place the binary at `/config/copilot` or `/config/bin/copilot` to persist across updates (these paths are automatically discovered by the integration), or in `/usr/local/bin/copilot`. Example for Alpine/amd64:
  ```bash
  apk add --no-cache curl ca-certificates
  # Option 1: Place at /config/bin/copilot (persists, automatically discovered)
  mkdir -p /config/bin
  curl -L https://github.com/github/copilot-cli/releases/latest/download/copilot-linux-amd64 -o /config/bin/copilot
  chmod +x /config/bin/copilot
  /config/bin/copilot --version
  /config/bin/copilot auth login
  
  # Option 2: Place at /usr/local/bin/copilot (requires reinstall on updates)
  curl -L https://github.com/github/copilot-cli/releases/latest/download/copilot-linux-amd64 -o /usr/local/bin/copilot
  chmod +x /usr/local/bin/copilot
  copilot --version
  copilot auth login
  ```
  For Debian/Ubuntu containers, adapt with `apt-get` and the matching binary for your architecture.
- Persist auth/config:
  ```bash
  mkdir -p /config/.gh_config
  mv /root/.config/gh/* /config/.gh_config/ 2>/dev/null || true
  export GH_CONFIG_DIR=/config/.gh_config
  ```
- Auto-reinstall on boot with a shell command + automation (only needed if you used Option 2 - `/usr/local/bin`):
  ```yaml
  # configuration.yaml (automation can be in automations.yaml if split)
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
  **Note**: If you used Option 1 (`/config/bin`), this automation is not needed as the binary already persists.

### Authentication Errors

**Issue**: "Invalid GitHub token" or "Authentication failed" error during setup

**Solutions**:
- Verify your GitHub token is correct and not expired
- Ensure your GitHub Copilot subscription is active
- Check that the token has necessary permissions (Copilot access)
- Run `copilot auth login` to authenticate the CLI
- Try generating a new personal access token

### Connection Errors

**Issue**: "Unable to connect to GitHub Copilot SDK" or communication errors

**Solutions**:
- Check your internet connection
- Verify Home Assistant can reach external APIs
- Ensure the Copilot CLI is properly installed and authenticated
- Check GitHub API status at https://www.githubstatus.com/
- Review Home Assistant logs (`Settings` → `System` → `Logs`) for detailed error messages

### No Response or Slow Responses

**Issue**: Conversation takes too long or times out

**Solutions**:
- Try a faster model (GPT-3.5 Turbo or GPT-4o-mini)
- Check your network latency
- Verify API rate limits aren't exceeded
- Check if the Copilot service is experiencing issues

### Conversation History Issues

**Issue**: Agent doesn't remember previous messages

**Solutions**:
- Ensure you're using the same `conversation_id` in service calls
- Check that conversation history isn't being reset
- Review integration logs for memory-related issues

## API Limits and Rate Limiting

GitHub Copilot has rate limits:

- Requests per minute: Varies by subscription tier
- Tokens per minute: Varies by subscription tier
- If you hit rate limits, responses will be delayed or fail

**Best Practices**:
- Implement delays between automated requests
- Monitor your API usage through GitHub

## Privacy and Data

- Conversations are sent to GitHub Copilot via the SDK
- GitHub's privacy policy applies to all API interactions
- Conversation history is stored locally in Home Assistant memory
- No conversation data is stored permanently by this integration

## Support and Contributions

### Reporting Issues

If you encounter issues:

1. Check the troubleshooting section
2. Review Home Assistant logs (`Settings` → `System` → `Logs`)
3. Open an issue on GitHub with:
   - Description of the problem
   - Relevant log entries
   - Home Assistant version
   - Integration version

### Contributing

Contributions are welcome! See `CONTRIBUTING.md` for guidelines.

### Repository

- GitHub: https://github.com/tserra30/Github-Copilot-SDK-integration
- Issues: https://github.com/tserra30/Github-Copilot-SDK-integration/issues

## Changelog

### Version 1.0.0

- Initial release
- Conversation agent support
- Multi-model support (GPT-4, GPT-4 Turbo, GPT-3.5 Turbo)
- Configurable parameters (model selection)
- Conversation history management
- HACS compatibility

## License

This integration is released under the GNU GPLv3. See `LICENSE` file for details.

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

- Built on Home Assistant's conversation agent framework
- Uses GitHub Copilot SDK
- Based on the Home Assistant integration blueprint by @ludeeus

---

**Note**: This integration is not officially affiliated with GitHub or Microsoft. GitHub Copilot is a trademark of GitHub, Inc.
