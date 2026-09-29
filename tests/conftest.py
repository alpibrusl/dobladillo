"""Make the CLI's human output the same everywhere the tests run.

Typer forces a colour terminal when it sees `GITHUB_ACTIONS` and wraps its
error panels to the terminal width, so in CI "Missing option '--tip-radius'"
came back as ANSI codes cut off with an ellipsis, and the tests that check a
refusal names the missing option failed there and nowhere else. Typer reads
these variables when it is first imported, which is why they are set here,
before any test module imports the CLI.
"""

import os

os.environ["_TYPER_FORCE_DISABLE_TERMINAL"] = "1"
os.environ["TERMINAL_WIDTH"] = "200"
