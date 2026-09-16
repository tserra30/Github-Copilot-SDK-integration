"""Exercise the add-on startup script with Bashio's strict shell settings."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

_BASH = shutil.which("bash")
_SCRIPT = Path(__file__).resolve().parents[1] / "addon" / "run.sh"
_FIXTURE = r"""
set -Eeuo pipefail
bashio::config() {
    case "$1" in
        github_token) printf '%s' "$TEST_GITHUB_TOKEN" ;;
        mcp_config) printf '' ;;
    esac
}
bashio::var.is_empty() { [[ -z "$1" ]]; }
bashio::log.info() { printf '%s\n' "$*"; }
bashio::log.warning() { printf '%s\n' "$*"; }
bashio::log.fatal() { printf '%s\n' "$*" >&2; }
timeout() { printf 'unexpected auth probe' > "$TEST_CALLS/probe"; return 1; }
sleep() { :; }
copilot() {
    case "$*" in
        "--version") printf 'GitHub Copilot CLI 1.0.83.\n'; return 0 ;;
        "--help"|"--headless --help")
            printf '%s\n' '  --no-auto-update  Disable updates' \
                '  --log-level <level>  Logging'
            return 0
            ;;
        "-p "*|"auth status")
            printf 'unexpected auth probe' > "$TEST_CALLS/probe"
            return 1
            ;;
    esac
    local attempt=1
    if [[ -f "$TEST_CALLS/count" ]]; then
        attempt=$(( $(<"$TEST_CALLS/count") + 1 ))
    fi
    printf '%s' "$attempt" > "$TEST_CALLS/count"
    printf '%s\n' "$@" > "$TEST_CALLS/$attempt"
    if [[ -z "${COPILOT_CONNECTION_TOKEN:-}" ]]; then
        printf 'Warning: No COPILOT_CONNECTION_TOKEN was set\n' >&2
    fi
    if (( attempt <= TEST_FAILURES )); then
        return 23
    fi
    return 0
}
source "$1"
"""


@skipUnless(os.name == "posix" and _BASH, "Add-on startup requires Linux Bash")
class AddonStartupTests(TestCase):
    """Keep startup failures observable and retries bounded under errexit."""

    def _run(
        self,
        *,
        failures: int = 0,
        configured_token: bool = True,
        connection_token: str = "",
    ) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
        with TemporaryDirectory() as directory:
            env = {
                **os.environ,
                "TEST_CALLS": directory,
                "TEST_FAILURES": str(failures),
                "TEST_GITHUB_TOKEN": "fixture-value" if configured_token else "",
                "COPILOT_CONNECTION_TOKEN": connection_token,
            }
            result = subprocess.run(  # noqa: S603 - Runs repository-owned Bash.
                [_BASH, "-c", _FIXTURE, "addon-test", str(_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            count_path = Path(directory) / "count"
            count = int(count_path.read_text()) if count_path.exists() else 0
            calls = [
                (Path(directory) / str(attempt)).read_text().splitlines()
                for attempt in range(1, count + 1)
            ]
            self.assertFalse(
                (Path(directory) / "probe").exists(),
                "Bridge startup must not make a model or legacy auth request",
            )
        return result, calls

    def test_server_failure_retries_under_errexit(self) -> None:
        """A transient server failure must not bypass the retry loop."""
        result, calls = self._run(failures=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 3)
        self.assertIn("attempt 3", result.stdout)

    def test_host_binding_does_not_depend_on_hidden_help(self) -> None:
        """The pinned CLI needs --host even though it does not advertise it."""
        result, calls = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0],
            [
                "--headless",
                "--host",
                "0.0.0.0",  # noqa: S104 - Expected container-only listener argument.
                "--port",
                "8000",
                "--no-auto-update",
                "--log-level",
                "info",
            ],
        )
        self.assertNotIn("--bind", calls[0])
        self.assertIn("0.0.0.0:8000", result.stdout)

    def test_retry_limit_preserves_failure_exit_code(self) -> None:
        """Repeated startup failures stop after the documented maximum."""
        result, calls = self._run(failures=10)
        self.assertEqual(result.returncode, 23)
        self.assertEqual(len(calls), 5)
        self.assertIn("failed after 5 attempts", result.stderr)

    def test_missing_token_never_starts_server(self) -> None:
        """Missing authentication is reported before launching the CLI."""
        result, calls = self._run(configured_token=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(calls)
        self.assertIn("No GitHub token configured", result.stderr)

    def test_configured_token_is_not_reported_as_validated(self) -> None:
        """Keep the real bridge warning, with context about its separate purpose."""
        result, _ = self._run()
        self.assertEqual(result.returncode, 0)
        self.assertIn("GitHub token configured", result.stdout)
        self.assertIn("not validated during bridge startup", result.stdout)
        self.assertIn("GitHub Copilot CLI 1.0.83", result.stdout)
        self.assertIn("separate from GitHub authentication", result.stdout)
        self.assertIn("Any client that can reach port 8000 may connect", result.stdout)
        self.assertIn("Home Assistant logs", result.stdout)
        self.assertIn("Warning: No COPILOT_CONNECTION_TOKEN", result.stderr)
        self.assertNotIn("auth probe failed", result.stdout)
        self.assertNotIn("fixture-value", result.stdout + result.stderr)

    def test_connection_token_notice_does_not_log_the_secret(self) -> None:
        """Report a configured handshake secret without disclosing its value."""
        private_value = "private-connection-fixture"
        result, calls = self._run(connection_token=private_value)
        self.assertEqual(result.returncode, 0)
        self.assertIn("SDK clients must provide the matching secret", result.stdout)
        self.assertNotIn("authentication is not configured", result.stdout)
        self.assertNotIn(private_value, result.stdout + result.stderr)
        self.assertNotIn(private_value, str(calls))
