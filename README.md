# GitHub Copilot Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

_Integration to bring GitHub Copilot AI capabilities to Home Assistant._

**This integration provides a conversation agent powered by GitHub Copilot, enabling voice assistants and AI-powered tasks similar to OpenAI, Claude, and Gemini integrations.**

## Features

- 🤖 **Conversation Agent** - Use GitHub Copilot as an AI conversation agent
- 🎤 **Voice Assistant Support** - Works with Home Assistant's voice pipeline
- 🔐 **Secure OAuth Authentication** - Uses GitHub's secure device flow (same as VS Code)
- 🔄 **Automatic Token Refresh** - Tokens refresh automatically, no manual intervention needed
- 🔧 **Configurable Models** - Support for GPT-4o, GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, and Claude 3.7 Sonnet
- ⚙️ **Customizable Parameters** - Adjust temperature, max tokens, and more via options
- 💬 **Context Preservation** - Maintains conversation history within sessions

## Requirements

- **GitHub Account** with an active [GitHub Copilot subscription](https://github.com/features/copilot)
- Home Assistant 2024.1.0 or newer

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
4. Click **Submit** to start the authentication process
5. You'll see a verification code - visit [github.com/login/device](https://github.com/login/device) and enter the code
6. Authorize the application in your browser
7. Return to Home Assistant and click **Submit** to confirm
8. Configure your preferred settings:
   - **Model**: Select from GPT-4o (default), GPT-4o-mini, GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, o3-mini, o1, o1-mini, Claude 3.5 Sonnet, or Claude 3.7 Sonnet
   - **Maximum Tokens**: Response length (100-4000)
   - **Temperature**: Creativity level (0=focused, 2=creative)

### Changing Settings

You can change model settings at any time:

1. Go to **Settings** → **Devices & Services**
2. Find the **GitHub Copilot** integration
3. Click **Configure**
4. Adjust your settings and save

### Re-authentication

If your authentication expires or is revoked:

1. Home Assistant will prompt you to re-authenticate
2. Follow the same device flow process as initial setup
3. Your settings will be preserved

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

## Model Selection Guide

| Model | Best For | Notes |
|-------|----------|-------|
| **GPT-4o** | General use, balanced performance | Default, recommended |
| **GPT-4o-mini** | Faster responses, lower cost | Good for simple queries |
| **GPT-4** | Complex reasoning | Slower but thorough |
| **GPT-4 Turbo** | Long context, faster GPT-4 | Good balance |
| **GPT-3.5 Turbo** | Basic queries, fastest | Limited capabilities |
| **o3-mini** | Reasoning tasks | No temperature support |
| **o1 / o1-mini** | Advanced reasoning | No temperature support |
| **Claude 3.5/3.7 Sonnet** | Alternative AI style | Temperature 0-1 only |

## Documentation

For detailed documentation, see [agents.md](agents.md)

## Troubleshooting

### Authentication Issues

- **"No active GitHub Copilot subscription"**: Ensure your GitHub account has an active Copilot subscription
- **"Authorization denied"**: You may have clicked "Cancel" during authorization - try again
- **"Authorization not yet completed"**: Complete the authorization in your browser before clicking Submit

### Connection Issues

- **Timeout errors**: Check your internet connection and try again
- **"Unable to connect"**: GitHub API may be experiencing issues - check [status.github.com](https://status.github.com)

### Response Issues

- **Slow responses**: Try using a faster model (GPT-4o-mini or GPT-3.5 Turbo)
- **Truncated responses**: Increase the max_tokens setting
- **Repetitive responses**: Increase the temperature setting

For more help, see the [agents.md](agents.md) documentation or [open an issue][issues].

## Privacy & Security

- This integration uses GitHub's official OAuth device flow
- Your GitHub credentials are never stored - only OAuth tokens
- Tokens are stored securely in Home Assistant's configuration
- Copilot API tokens auto-refresh and expire after a short period
- You can revoke access at any time from [GitHub Settings](https://github.com/settings/applications)

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the GNU GPLv3 - see the [LICENSE](LICENSE) file for details.
Some source code was originally licensed under the MIT license.

## Acknowledgments

- Built on Home Assistant's conversation framework
- Based on the integration blueprint by [@ludeeus](https://github.com/ludeeus)

---

**Note**: This integration is not officially affiliated with GitHub or Microsoft.

## Original MIT license from integration blueprint by [@ludeeus](https://github.com/ludeeus)

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

[commits-shield]: https://img.shields.io/github/commit-activity/y/tserra30/Github-Copilot-SDK-integration.svg?style=for-the-badge
[commits]: https://github.com/tserra30/Github-Copilot-SDK-integration/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/tserra30/Github-Copilot-SDK-integration.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/tserra30/Github-Copilot-SDK-integration.svg?style=for-the-badge
[releases]: https://github.com/tserra30/Github-Copilot-SDK-integration/releases
[issues]: https://github.com/tserra30/Github-Copilot-SDK-integration/issues
