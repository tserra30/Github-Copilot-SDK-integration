# GitHub Copilot Bridge Add-on Changelog

All notable changes to the GitHub Copilot Bridge add-on will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- No add-on changes yet.

## [v3.9.8] - 2026-04-30

### Changed
- **Version bump to align with integration release v3.9.8**
  - No add-on-specific changes in this release
  - Integration updates include new AI models (GPT-4.1, GPT-5, Claude Sonnet 4.5, Claude Haiku 4.5, Claude Opus 4.6) and session-leak fixes

## [v3.9.4] - 2026-04-10

### Added
- **Add icon and logo images** to add-on directory so the add-on displays its icon and logo in Home Assistant

## [v3.9.2] - 2026-04-03

### Changed
- **Version bump to align with integration release v3.9.2**
  - No add-on-specific changes in this release
  - Integration updates include improved DNS error messages when connecting to the bridge add-on and a fix to the SDK wheel URL requirement format

## [v3.9.0] - 2026-04-02

### Changed
- **Version bump to align with integration release v3.9.0**
  - No add-on-specific changes in this release
  - Integration updates include an improved GitHub Pages site with responsive design and dark mode

## [v3.8.8] - 2026-04-05

### Changed
- **Version bump to align with integration release v3.8.8**
  - No add-on-specific changes in this release
  - Integration updates include the patched `github-copilot-sdk 0.1.22+ha` universal wheel (auto-installed from `manifest.json`) to fix Home Assistant OS installation failures

## [v3.8.3] - 2026-04-01

### Changed
- **Updated GitHub Copilot CLI from v1.0.9 to v1.0.13** ([#105](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/105))
  - Brings protocol v3 support for compatibility with github-copilot-sdk 0.1.32
  - Maintains backward compatibility with protocol v2
  - Uses SHA256 verification from release's own `SHA256SUMS.txt` at build time

### Fixed
- **Enhanced CLI server stability** with improved retry mechanism and error handling
- **Fixed authentication flow** to work correctly with token-only setups when using the bridge add-on
- **Clarified SDK requirement for all modes** ([#107](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/107))
  - `github-copilot-sdk` is required in **both** bridge add-on and local CLI modes — it is the Python client library the integration uses to communicate with the CLI server in all configurations
  - Updated documentation to correct misleading guidance that implied add-on mode needed no SDK
  - The integration now auto-installs the patched `0.1.22+ha` universal wheel from `manifest.json` — no manual install required on any platform
  - The bridge add-on eliminates the need for a **local Copilot CLI binary**; the Python SDK is still required

## [v3.7.5] - 2026-03-25

### Fixed
- **Hardened authentication probe mechanism** ([#97](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/97))
  - Improved GH_TOKEN-based authentication reliability
  - Added timeout protection for authentication checks to prevent startup blocking
  - Enhanced probe logic to work with both new and legacy CLI versions
  - Added best-effort auth verification that doesn't block server startup

### Changed
- **Enhanced bind address configuration** ([#97](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/97))
  - Ensures server is reachable from other Supervisor-network containers
  - Added feature detection for optional CLI flags (`--bind`, `--no-auto-update`, `--log-level`)
  - Improved CLI flag compatibility across different pinned CLI versions

## [v3.6.0] - 2026-03-19

### Changed
- **Updated GitHub Copilot CLI from v0.5.1 to v1.0.9** ([#89](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/89))
  - Fixes 404 errors when downloading CLI binaries
  - Significant version jump brings latest stable CLI features
  - Updated to use new tarball asset format (.tar.gz) instead of direct binary downloads

## [v3.5.0] - 2026-03-03

### Changed
- **Migrated base image from Alpine to Debian Bullseye** ([#74](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/74), [#69](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/69))
  - Fixes glibc compatibility issues with GitHub Copilot CLI
  - Native glibc support eliminates compatibility shims
  - Debian base provides better stability for the CLI server

- **Updated GitHub Copilot CLI to v0.5.1** ([#74](https://github.com/tserra30/Github-Copilot-SDK-integration/pull/74))
  - Improves CLI reliability and feature support

### Fixed
- **Resolved addon crash issues** caused by Alpine/musl incompatibility with the Copilot CLI binary

## Earlier Versions

### Initial Release Features
- **Headless GitHub Copilot CLI server** running in dedicated container
- **Port 8000 server** on Home Assistant Supervisor internal network
- **Automatic GitHub authentication** via GH_TOKEN environment variable
- **Multi-architecture support** for amd64 and aarch64
- **Automatic retry mechanism** for server crashes (up to 5 retries)
- **SHA256 checksum verification** for CLI binary downloads
- **Auto-start on boot** with configurable GitHub token

---

## Integration Compatibility

The bridge add-on is designed to work seamlessly with the GitHub Copilot Home Assistant integration:

- **v3.9.8 (current)**: Compatible with integration v1.0.7 using the patched `github-copilot-sdk 0.1.22+ha` wheel (auto-installed; works on all platforms including HA OS)
- **v3.9.0 – v3.9.4**: Compatible with integration v1.0.6 using the patched `github-copilot-sdk 0.1.22+ha` wheel
- **v3.8.3 – v3.8.8**: Compatible with integration v1.0.6 using the patched `github-copilot-sdk 0.1.22+ha` wheel (auto-installed from `manifest.json`; works on all platforms including HA OS)
- **v3.7.5 – v3.6.0**: Compatible with integration v1.0.4 using github-copilot-sdk 0.1.22
- **Earlier versions**: Compatible with older integration versions

For best results, always use the latest versions of both the add-on and the integration.

## Notes

- The add-on requires a valid GitHub Personal Access Token with Copilot permissions (provided to the add-on as `GH_TOKEN`)
- When the Home Assistant integration is configured in remote/bridge mode (`cli_url` set), it does not store or pass a GitHub token; authentication is handled entirely by the bridge add-on via its own `GH_TOKEN`
- The add-on URL format is `http://<hostname>:8000` where hostname can be found in the add-on Info tab
- The bridge add-on is especially useful for Home Assistant OS users where manual CLI installation is challenging

[v3.9.8]: https://github.com/tserra30/Github-Copilot-SDK-integration/compare/v3.9.4...v3.9.8
[v3.9.4]: https://github.com/tserra30/Github-Copilot-SDK-integration/compare/v3.9.2...v3.9.4
[v3.9.2]: https://github.com/tserra30/Github-Copilot-SDK-integration/compare/v3.9.0...v3.9.2
[v3.9.0]: https://github.com/tserra30/Github-Copilot-SDK-integration/compare/v3.8.8...v3.9.0
[v3.8.8]: https://github.com/tserra30/Github-Copilot-SDK-integration/compare/v3.8.3...v3.8.8
[v3.8.3]: https://github.com/tserra30/Github-Copilot-SDK-integration/compare/v3.7.5...v3.8.3
[v3.7.5]: https://github.com/tserra30/Github-Copilot-SDK-integration/releases/tag/v3.7.5
[v3.6.0]: https://github.com/tserra30/Github-Copilot-SDK-integration/releases/tag/v3.6.0
[v3.5.0]: https://github.com/tserra30/Github-Copilot-SDK-integration/releases/tag/v3.5.0
