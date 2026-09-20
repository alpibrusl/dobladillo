"""Command line entry point.

Kept thin on purpose: every command is a call into a library function that is
usable and testable without the CLI.
"""

from __future__ import annotations

import typer

from dobladilo import __version__

app = typer.Typer(help="DNA origami brick toolchain.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Group the commands under subcommands.

    Without a callback, typer collapses a single `@app.command()` into the root
    command, so `dobladilo version` fails with "unexpected extra argument" and
    only starts working once a second command happens to be added. Declaring
    the callback fixes the shape now rather than on the day that happens.
    """


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
