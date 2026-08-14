"""Installed HumanHand CLI root.

The legacy application remains import-compatible for existing tests and
integrations. The installed console entry point adds the EP-019 integrated
``workflow`` command family without duplicating or replacing legacy commands.
"""

from humanhand.cli.app import app
from humanhand.cli.workflow_commands import workflow_app

app.add_typer(workflow_app, name="workflow")

__all__ = ["app"]
