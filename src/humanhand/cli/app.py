"""Typer CLI application."""

from __future__ import annotations

import json
import sys

import typer

from humanhand import __version__
from humanhand.cli.output import render_health
from humanhand.infra.config import Config, load_config

app = typer.Typer(
    name="humanhand",
    help="Privacy-preserving CLI for rewriting AI-assisted text into human style.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        print(f"humanhand {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """Human Hand CLI — rewrite AI-assisted text into human style."""


@app.command()
def health(
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
) -> None:
    """Check CLI health without network calls or user text."""
    try:
        config = load_config()
    except Exception:
        config = Config()

    if json_mode:
        result = {
            "status": "ok",
            "version": __version__,
            "python_version": sys.version,
        }
        print(json.dumps(result))
    else:
        render_health(config)
