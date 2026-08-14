"""E2E coverage for the production `humanhand workflow` command family."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import typer
from typer.testing import CliRunner

from humanhand.application.integrated_workflow import load_document_state
from humanhand.cli.workflow_commands import workflow_app
from humanhand.domain.document_nodes import NodeType
from humanhand.domain.lexical_normalizer import proposal_from_payload
from humanhand.infra.stores.integrated_project_store import IntegratedProjectStore

cli_app = typer.Typer()
cli_app.add_typer(workflow_app, name="workflow")

runner = CliRunner()


def _invoke(*args: str) -> Any:
    return runner.invoke(cli_app, ["workflow", *args])


def _json_output(stdout: str) -> dict[str, Any]:
    value: object = json.loads(stdout)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_complete_workflow_cli_lifecycle(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text(
        "We utilize the available evidence on August 30, 2026.",
        encoding="utf-8",
        newline="\n",
    )
    project = tmp_path / "project"

    ingest = _invoke(
        "ingest",
        str(source),
        "--project",
        str(project),
        "--name",
        "Workflow Project",
        "--json",
    )
    assert ingest.exit_code == 0, ingest.stderr
    ingested = _json_output(ingest.stdout)
    project_id = str(ingested["project_id"])
    document_id = str(ingested["document_id"])
    assert ingested["style_profile"] == ""
    assert ingested["encrypted_retention"] is False

    store = IntegratedProjectStore(project)
    try:
        loaded = load_document_state(
            project_id=project_id,
            document_id=document_id,
            store=store,
        )
        block_id = next(
            node.node_id for node in loaded.document.nodes if node.node_type is NodeType.PARAGRAPH
        )
    finally:
        store.close()

    context_summary = _invoke(
        "context",
        "--project",
        str(project),
        "--document",
        document_id,
        "--block",
        block_id,
        "--json",
    )
    assert context_summary.exit_code == 0, context_summary.stderr
    summary = _json_output(context_summary.stdout)
    assert summary["status"] == "ok"
    assert summary["document_id"] == document_id
    assert summary["content_included"] is False

    context_content = _invoke(
        "context",
        "--project",
        str(project),
        "--document",
        document_id,
        "--block",
        block_id,
        "--include-content",
        "--json",
    )
    assert context_content.exit_code == 0, context_content.stderr
    included = _json_output(context_content.stdout)
    assert included["document_id"] == document_id
    assert included["block_id"] == block_id

    proposed = _invoke(
        "propose",
        "--project",
        str(project),
        "--document",
        document_id,
        "--json",
    )
    assert proposed.exit_code == 0, proposed.stderr
    proposal_result = _json_output(proposed.stdout)
    run_id = str(proposal_result["run_id"])
    proposal_path = Path(str(proposal_result["proposal_path"]))
    proposal = proposal_from_payload(json.loads(proposal_path.read_text(encoding="utf-8")))
    change = next(item for item in proposal.changes if item.source_surface.lower() == "utilize")

    bad_decision = _invoke(
        "decide",
        "--run",
        run_id,
        "--change",
        change.change_id,
        "--decision",
        "maybe",
        "--project",
        str(project),
        "--json",
    )
    assert bad_decision.exit_code == 1
    assert _json_output(bad_decision.stdout)["exit_code"] == 1

    rejected = _invoke(
        "decide",
        "--run",
        run_id,
        "--change",
        change.change_id,
        "--decision",
        "reject",
        "--project",
        str(project),
        "--json",
    )
    assert rejected.exit_code == 0, rejected.stderr
    assert _json_output(rejected.stdout)["decision"] == "reject"

    accepted = _invoke(
        "decide",
        "--run",
        run_id,
        "--change",
        change.change_id,
        "--decision",
        "accept",
        "--project",
        str(project),
        "--json",
    )
    assert accepted.exit_code == 0, accepted.stderr
    assert _json_output(accepted.stdout)["decision"] == "accept"

    applied = _invoke(
        "apply",
        "--run",
        run_id,
        "--project",
        str(project),
        "--document",
        document_id,
        "--json",
    )
    assert applied.exit_code == 0, applied.stderr
    application = _json_output(applied.stdout)
    assert application["accepted_changes"] == 1
    assert application["style_checked"] is False

    bad_export = _invoke(
        "export",
        "--project",
        str(project),
        "--document",
        document_id,
        "--format",
        "bogus",
        "--out",
        str(tmp_path / "bogus.out"),
        "--json",
    )
    assert bad_export.exit_code == 1
    assert "Unknown export format" in str(_json_output(bad_export.stdout)["message"])

    output = tmp_path / "final.txt"
    exported = _invoke(
        "export",
        "--project",
        str(project),
        "--document",
        document_id,
        "--format",
        "txt",
        "--out",
        str(output),
        "--title",
        "Workflow Project",
        "--json",
    )
    assert exported.exit_code == 0, exported.stderr
    export_result = _json_output(exported.stdout)
    assert export_result["audit"]["status"] == "pass"
    assert export_result["internal_claims_included"] is False
    rendered = output.read_text(encoding="utf-8")
    assert "utilize" not in rendered.lower()
    assert "use the available evidence" in rendered.lower()
    assert "August 30, 2026" in rendered

    status = _invoke("status", "--project", str(project), "--json")
    assert status.exit_code == 0, status.stderr
    status_result = _json_output(status.stdout)
    assert status_result["project_id"] == project_id
    assert status_result["style_profile"] is None
    assert status_result["documents"] == [
        {
            "accepted_revision": application["revision_id"],
            "content_persisted": True,
            "document_id": document_id,
            "finalization_run_id": run_id,
        }
    ]
