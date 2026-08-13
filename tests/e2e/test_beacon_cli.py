"""E2E tests for the `humanhand beacon` sub-app (EP-018).

The beacon CLI imports its domain/infra surface lazily so incomplete wheel
installations fail closed. These tests exercise the complete EP-018 surface.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from humanhand.cli.beacon_commands import beacon_app
from humanhand.domain.beacon_evidence import EvidenceSet, create_evidence
from humanhand.domain.beacon_policy import action_category_for_kind, review_proposal
from humanhand.domain.beacon_proposals import ProposalKind, create_proposal
from humanhand.domain.beacon_types import (
    BeaconTriggerType,
    EvidenceTrustTier,
    create_trigger,
)
from humanhand.infra.beacon.policy_loader import load_allowed_actions, load_blocked_actions
from humanhand.infra.beacon.proposal_store import ProposalStore

pytestmark = pytest.mark.importers

# Standalone composed app: tests never touch the orchestrator (app.py).
cli_app = typer.Typer()
cli_app.add_typer(beacon_app, name="beacon")
runner = CliRunner()


def _module_present(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        # A parent package in the chain is absent -> the module is absent.
        return False


_BEACON_MODULES = (
    "humanhand.domain.beacon_types",
    "humanhand.domain.beacon_evidence",
    "humanhand.infra.beacon.snapshot_store",
)

NEED_BEACON = pytest.mark.skipif(
    not all(_module_present(name) for name in _BEACON_MODULES),
    reason="EP-018 parallel beacon modules are not all present yet",
)


def _proposal_store_has_surface() -> bool:
    """True only when the proposal store exposes the CLI's documented surface.

    The parallel proposal store module may exist while lacking the
    ``load_proposal``/``append_decision`` methods this CLI calls; the
    firewall tests only activate once the full contract is present.
    """
    try:
        module = importlib.import_module("humanhand.infra.beacon.proposal_store")
    except ModuleNotFoundError:
        return False
    store_cls = getattr(module, "ProposalStore", None)
    if store_cls is None:
        return False
    return hasattr(store_cls, "load_proposal") and hasattr(store_cls, "append_decision")


NEED_PROPOSALS = pytest.mark.skipif(
    not _proposal_store_has_surface(),
    reason=(
        "proposal store does not yet expose the documented load_proposal/append_decision surface"
    ),
)
ONLY_WITHOUT_BEACON = pytest.mark.skipif(
    all(_module_present(name) for name in _BEACON_MODULES),
    reason="parallel beacon modules are present; fail-closed tests no longer apply",
)


@ONLY_WITHOUT_BEACON
def test_beacon_run_fails_closed_without_parallel_modules(tmp_path: Path) -> None:
    """Without the parallel modules the command fails closed, exit 2, honest."""
    result = runner.invoke(
        cli_app,
        ["beacon", "run", "--state", str(tmp_path / "beacon")],
    )
    assert result.exit_code == 2
    assert "not available in this build" in result.stderr
    assert "missing module: humanhand.domain.beacon" in result.stderr


@ONLY_WITHOUT_BEACON
def test_beacon_run_fails_closed_json_mode(tmp_path: Path) -> None:
    """JSON mode reports the fail-closed error as a JSON error payload."""
    result = runner.invoke(
        cli_app,
        ["beacon", "run", "--state", str(tmp_path / "beacon"), "--json"],
    )
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["exit_code"] == 2
    assert "not available in this build" in payload["message"]


@NEED_BEACON
def test_beacon_run_creates_offline_snapshot(tmp_path: Path) -> None:
    """`beacon run` stores an offline snapshot and returns its ids."""
    result = runner.invoke(
        cli_app,
        ["beacon", "run", "--state", str(tmp_path / "beacon"), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["schema_version"] == 1
    assert payload["investigation_id"].startswith("trig-")
    assert payload["trigger_type"] == "security_advisory"
    assert payload["snapshot_id"]


@NEED_BEACON
def test_beacon_report_lists_snapshots(tmp_path: Path) -> None:
    """`beacon report <investigation-id>` lists the stored snapshots."""
    run_result = runner.invoke(
        cli_app,
        ["beacon", "run", "--state", str(tmp_path / "beacon"), "--json"],
    )
    assert run_result.exit_code == 0
    run_payload = json.loads(run_result.stdout)
    investigation_id = run_payload["investigation_id"]
    report_result = runner.invoke(
        cli_app,
        ["beacon", "report", investigation_id, "--state", str(tmp_path / "beacon"), "--json"],
    )
    assert report_result.exit_code == 0
    report = json.loads(report_result.stdout)
    assert report["investigation_id"] == investigation_id
    assert report["count"] >= 1
    assert report["snapshots"][0]["snapshot_id"] == run_payload["snapshot_id"]


@NEED_BEACON
def test_beacon_sources_reports_registry(tmp_path: Path) -> None:
    """`beacon sources <investigation-id>` returns the evidence source registry."""
    run_result = runner.invoke(
        cli_app,
        ["beacon", "run", "--state", str(tmp_path / "beacon"), "--json"],
    )
    assert run_result.exit_code == 0
    investigation_id = json.loads(run_result.stdout)["investigation_id"]
    result = runner.invoke(
        cli_app,
        [
            "beacon",
            "sources",
            investigation_id,
            "--state",
            str(tmp_path / "beacon"),
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["investigation_id"] == investigation_id
    assert payload["count"] >= 1
    for source in payload["sources"]:
        assert source["source_id"]
        assert source["tier"]
        assert source["label"]


def _write_proposal(state_dir: Path, blocked: bool) -> str:
    """Create, policy-review, and persist a schema-valid proposal."""
    trigger = create_trigger(BeaconTriggerType.SECURITY_ADVISORY, "test advisory")
    evidence = create_evidence(
        trigger_id=trigger.trigger_id,
        tier=EvidenceTrustTier.TIER_4_TECHNICAL_ANALYSIS,
        source_kind="advisory",
        summary="public advisory",
        url="https://example.org/advisory",
        snippet_sha256="a" * 64,
    )
    proposal = create_proposal(
        trigger=trigger,
        kind=ProposalKind.METADATA_FIELD,
        summary="test proposal",
        evidence=EvidenceSet((evidence,)),
        high_impact=False,
    )
    blocked_actions = load_blocked_actions()
    if blocked:
        blocked_actions |= {action_category_for_kind(proposal.kind)}
    reviewed = review_proposal(
        proposal,
        allowed_actions=load_allowed_actions(),
        blocked_actions=blocked_actions,
    )
    ProposalStore(state_dir).store_proposal(reviewed)
    return reviewed.proposal_id


@NEED_PROPOSALS
def test_approve_blocked_proposal_is_refused(tmp_path: Path) -> None:
    """ADR-006: a firewall-blocked proposal cannot be approved (exit 1)."""
    state_dir = tmp_path / "beacon"
    proposal_id = _write_proposal(state_dir, blocked=True)
    result = runner.invoke(
        cli_app,
        ["beacon", "approve", proposal_id, "--state", str(state_dir)],
    )
    assert result.exit_code == 1
    assert "blocked by the research beacon firewall" in result.stderr


@NEED_PROPOSALS
def test_approve_allowed_proposal_succeeds(tmp_path: Path) -> None:
    """An unblocked proposal can be approved."""
    state_dir = tmp_path / "beacon"
    proposal_id = _write_proposal(state_dir, blocked=False)
    result = runner.invoke(
        cli_app,
        ["beacon", "approve", proposal_id, "--state", str(state_dir), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["decision"] == "approve"
    assert payload["blocked_action"] is False


@NEED_PROPOSALS
def test_deny_blocked_proposal_is_allowed(tmp_path: Path) -> None:
    """Denial is always allowed, including for firewall-blocked proposals."""
    state_dir = tmp_path / "beacon"
    proposal_id = _write_proposal(state_dir, blocked=True)
    result = runner.invoke(
        cli_app,
        ["beacon", "deny", proposal_id, "--state", str(state_dir), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["decision"] == "deny"
    assert payload["blocked_action"] is True


@NEED_PROPOSALS
def test_approve_missing_proposal_fails(tmp_path: Path) -> None:
    """Approving a nonexistent proposal fails with a non-zero exit."""
    result = runner.invoke(
        cli_app,
        ["beacon", "approve", "prop-9999", "--state", str(tmp_path / "beacon")],
    )
    assert result.exit_code != 0
