# GitHub Copilot Home Assistant Integration - Agents Documentation

## Overview

This integration adds GitHub Copilot AI capabilities to Home Assistant, enabling voice assistants and other AI-powered tasks similar to OpenAI, Claude, and Gemini integrations.

## Features

- **Conversation Agent**: Use GitHub Copilot as a conversation agent in Home Assistant
- **Voice Assistant Support**: Compatible with Home Assistant's voice assistant pipeline
- **Configurable Models**: Support for multiple GPT models (GPT-4, GPT-4 Turbo, GPT-3.5 Turbo)
- **Customizable Parameters**: Adjust temperature, max tokens, and other AI parameters
- **Context Preservation**: Maintains conversation history within sessions

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
   - **API Token**: Your GitHub Copilot API token
   - **Model**: Select the AI model (default: GPT-4)
   - **Maximum Tokens**: Set response length limit (100-4000, default: 1000)
   - **Temperature**: Control creativity (0-2, default: 0.7)
     - Lower values (0-0.5): More focused and deterministic
     - Higher values (0.8-2): More creative and varied

### Getting a GitHub Copilot API Token

To use this integration, you need a GitHub personal access token with Copilot access:

1. Ensure you have an active GitHub Copilot subscription
2. Visit [GitHub token settings](https://github.com/settings/tokens)
3. Generate a new token with these permissions:
   - `read:user` - to access user information
   - `copilot` - for Copilot API access (if available)
4. Copy and save the token securely

**How Authentication Works**:
The integration uses a two-step authentication process:
1. Your GitHub PAT is exchanged for a Copilot-specific token
2. The Copilot token is used for all chat API requests
3. Tokens are cached for efficiency (approximately 2 hours)

**Note**: Keep your API token secure and never share it publicly.

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

- **GPT-4**: Most capable, best reasoning and instruction following
- **GPT-4 Turbo**: Faster responses, good balance of speed and capability
- **GPT-3.5 Turbo**: Fastest, suitable for simple conversations

### Temperature Settings

Adjust the creativity/randomness of responses:

- **0.0-0.3**: Highly focused, consistent, deterministic
- **0.4-0.7**: Balanced (recommended for most use cases)
- **0.8-1.5**: Creative, varied responses
- **1.6-2.0**: Very creative, potentially unpredictable

### Maximum Tokens

Controls the length of responses:

- **100-500**: Short, concise answers
- **500-1500**: Standard responses (default: 1000)
- **1500-4000**: Longer, more detailed explanations

## Troubleshooting

### Authentication Errors

**Issue**: "Invalid API token" error during setup

**Solutions**:
- Verify your API token is correct
- Ensure your GitHub Copilot subscription is active
- Check that the token has necessary permissions
- Try generating a new token

### Connection Errors

**Issue**: "Unable to connect to GitHub Copilot API"

**Solutions**:
- Check your internet connection
- Verify Home Assistant can reach external APIs
- Check GitHub API status
- Review Home Assistant logs for detailed error messages

### No Response or Slow Responses

**Issue**: Conversation takes too long or times out

**Solutions**:
- Reduce `max_tokens` setting
- Try a faster model (GPT-3.5 Turbo)
- Check your network latency
- Verify API rate limits aren't exceeded

### Conversation History Issues

**Issue**: Agent doesn't remember previous messages

**Solutions**:
- Ensure you're using the same `conversation_id` in service calls
- Check that conversation history isn't being reset
- Review integration logs for memory-related issues

## API Limits and Rate Limiting

GitHub Copilot API has rate limits:

- Requests per minute: Varies by subscription tier
- Tokens per minute: Varies by subscription tier
- If you hit rate limits, responses will be delayed or fail

**Best Practices**:
- Use appropriate `max_tokens` values
- Implement delays between automated requests
- Monitor your API usage through GitHub

## Privacy and Data

- Conversations are sent to GitHub Copilot API
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
- Configurable parameters (temperature, max_tokens)
- Conversation history management
- HACS compatibility

## License

This integration is released under the GNU GPLv3. See `LICENSE` file for details.

## Acknowledgments

- Built on Home Assistant's conversation agent framework
- Uses GitHub Copilot API
- Based on the Home Assistant integration blueprint by @ludeeus

---

**Note**: This integration is not officially affiliated with GitHub or Microsoft. GitHub Copilot is a trademark of GitHub, Inc.
