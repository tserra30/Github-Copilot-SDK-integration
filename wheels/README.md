# Patched github-copilot-sdk Wheels

This directory contains patched versions of `github-copilot-sdk` built from version 0.1.22 source with the following modifications:

## Patches Applied

### 1. Protocol Version Update
- Changed `SDK_PROTOCOL_VERSION` from `2` to `3` in `copilot/sdk_protocol_version.py`
- Allows SDK to work with Copilot CLI v1.0.13 which reports protocol v3

### 2. Backward Compatibility
- Modified protocol version check in `copilot/client.py`
- Changed from strict equality (`server_version != expected_version`)
- To range check (`server_version not in [2, 3]`)
- Ensures SDK works with both protocol v2 and v3 servers

## Why This Approach?

- **SDK 0.1.22**: Has universal `py3-none-any` wheels that work on Home Assistant OS
- **SDK 0.1.23+**: Only have `manylinux_2_28` wheels requiring glibc ≥ 2.28
- **Home Assistant OS**: Has older glibc and cannot install SDK 0.1.23+
- **Protocol Issue**: SDK 0.1.22 only supports protocol v2, CLI v1.0.13 uses v3

## Build Process

The wheel is built using GitHub Actions workflow `.github/workflows/build-sdk.yml`:

1. Downloads SDK 0.1.22 source from PyPI
2. Applies patches to support protocol v3
3. Builds universal `py3-none-any` wheel
4. Commits wheel to repository

## Wheel Details

- **Filename**: `github_copilot_sdk-0.1.22+ha-py3-none-any.whl`
- **Base Version**: 0.1.22 (patched, with `+ha` local version identifier per PEP 440)
- **Wheel Type**: Universal (py3-none-any)
- **Compatible with**: All Python 3.x platforms including Home Assistant OS

## Installation

This wheel **is** installed automatically by Home Assistant from the integration's `manifest.json` requirements:

```json
"requirements": [
  "https://github.com/tserra30/Github-Copilot-SDK-integration/raw/fd973cc65828d677d69e8f2406a69aa140858cd8/wheels/github_copilot_sdk-0.1.22+ha-py3-none-any.whl#sha256=d2aad92a793bdd6d4a8b3ffee9b34255cadb8348be35c984f00cc6d2a5a3230f"
]
```

Home Assistant will download and install the wheel directly from the repository when the integration loads. The URL is pinned to an immutable commit SHA (`fd973cc65828d677d69e8f2406a69aa140858cd8`) with sha256 verification for reproducible, tamper-evident installs.

**Manual Installation (not normally needed):**

```bash
pip install "https://github.com/tserra30/Github-Copilot-SDK-integration/raw/fd973cc65828d677d69e8f2406a69aa140858cd8/wheels/github_copilot_sdk-0.1.22+ha-py3-none-any.whl#sha256=d2aad92a793bdd6d4a8b3ffee9b34255cadb8348be35c984f00cc6d2a5a3230f"
```

## Verification

To verify the patches were applied:

```python
import copilot
from copilot.sdk_protocol_version import SDK_PROTOCOL_VERSION

print(f"SDK Protocol Version: {SDK_PROTOCOL_VERSION}")
# Should print: SDK Protocol Version: 3
```
