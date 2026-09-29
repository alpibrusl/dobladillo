"""Run a CLI command in-process with `--json`: the one contract every front end uses.

The MCP server and the web UI both answer by running the matching command and
returning its payload, so neither can say something the command would not,
and a refusal reaches them with the command's own `error.kind`. This is the
single place that does the running.

`CliRunner` swaps the process's stdout while a command runs, so two commands
must never run at once: the web server answers requests on threads. The lock
makes the invocations one at a time, which a single-user local tool can
afford.
"""

from __future__ import annotations

import json
import threading
from typing import Any

_ONE_AT_A_TIME = threading.Lock()


def run_json(*args: str) -> tuple[int, dict[str, Any]]:
    """Run `dobladillo <args> --json`; return its exit code and payload."""
    from typer.testing import CliRunner

    from dobladillo.cli import app

    with _ONE_AT_A_TIME:
        result = CliRunner().invoke(app, [*args, "--json"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "error": {
                "kind": "no_json",
                "message": (result.stdout + (result.stderr or "")).strip()[-2000:]
                or repr(result.exception),
            }
        }
    if not isinstance(payload, dict):  # pragma: no cover - every command emits an object
        payload = {"error": {"kind": "no_json", "message": repr(payload)[:2000]}}
    return result.exit_code, payload
