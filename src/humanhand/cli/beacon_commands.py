"""`humanhand beacon` sub-app — research beacon (EP-018).

The orchestrator registers this module's ``beacon_app`` into
``humanhand.cli.app`` as the "beacon" sub-app at merge time; this module
never registers itself.

The CLI imports the EP-018 domain and infrastructure modules lazily so the
root command can still fail closed if an installation is incomplete:

- ``humanhand.domain.beacon_types``
    - ``BeaconTriggerType`` enum and deterministic ``create_trigger``
    - ``BeaconTrigger`` frozen dataclass with fields ``trigger_id``,
      ``trigger_type``, ``summary`` (the CLI supplies all fields)
- ``humanhand.infra.beacon.source_registry``
    - ``sources_for_trigger`` returns registered public sources
- ``humanhand.infra.beacon.snapshot_store``
    - ``SnapshotStore(root: Path)`` with ``store_snapshot`` and
      ``load_snapshots(trigger_id) -> tuple[SnapshotRecord, ...]``;
      ``SnapshotRecord`` has ``snapshot_id``, ``trigger_id``,
      ``trigger_type``, ``summary``
- ``humanhand.infra.beacon.proposal_store``
    - ``ProposalStore(root: Path)`` with
      ``load_proposal(proposal_id) -> RemediationProposal`` and
      ``append_decision(proposal_id, decision: dict)``;
      ``RemediationProposal`` has at least ``proposal_id``, ``action``,
      ``blocked_action``, ``evidence``, ``summary``
- proposal payloads are schema-validated by ``ProposalStore`` before the
  human decision gate is evaluated.

If any parallel module is absent at runtime, the affected commands fail
closed with exit code 2 and an honest "not available in this build
(missing module: X)" message; no stub is created.

``beacon run`` is fully offline: it never touches the network. The live
research-client path (``humanhand.infra.beacon.xai_research_client.XaiResearchClient``)
is documented by SPEC-015 but is deliberately NOT wired into this CLI
build; no credentials or endpoints are required.

``--no-color`` is accepted for CLI-surface compatibility; this module
never emits color codes, so the flag is a documented no-op.
"""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import typer

from humanhand.cli.errors import message_for_exception
from humanhand.domain.types import DomainError
from humanhand.infra.files import FileIOError

# Exit-code constants are duplicated here deliberately (app.py owns the
# canonical definitions; importing them would create an import cycle).
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3
EXIT_INTERNAL_ERROR = 6

DEFAULT_TRIGGER_TYPE = "security_advisory"
DEFAULT_SUMMARY = "offline investigation run"
DEFAULT_STATE_DIR = ".humanhand/beacon"
RESULT_SCHEMA_VERSION = 1

beacon_app = typer.Typer(
    name="beacon",
    help="Research beacon: offline trigger snapshots, source registry, and proposal decisions.",
    no_args_is_help=True,
)


def _effective_flag(ctx: typer.Context | None, local_value: bool, key: str) -> bool:
    """Resolve a flag from local options plus root callback state.

    Mirrors ``_effective_flag`` in app.py; duplicated to avoid an import
    cycle between app.py and this module.
    """
    if local_value:
        return True
    if ctx is None or not isinstance(ctx.obj, dict):
        return False
    return bool(ctx.obj.get(key, False))


def _report_error(message: str, code: int, json_mode: bool) -> NoReturn:
    """Emit a one-line error and exit with a stable code."""
    if json_mode:
        print(
            json.dumps(
                {"status": "error", "message": message, "exit_code": code},
                sort_keys=True,
            )
        )
    else:
        print(f"error: {message}", file=sys.stderr)
    raise typer.Exit(code)


def _render_json(payload: dict[str, object]) -> None:
    """Emit a JSON result to stdout.

    Rendering is intentionally local to this module: the orchestrator owns
    ``cli/output.py`` and may later route these results through its
    renderers; this helper keeps the command self-contained until then.
    """
    print(json.dumps(payload, sort_keys=True))


def _fail_closed(module_name: str, missing: str, json_mode: bool) -> NoReturn:
    """Honest fail-closed error (exit 2) when a parallel module is missing.

    Message mirrors the EP-015 precedent so scripts can match on it.
    """
    _report_error(
        f"{module_name} is not available in this build (missing module: {missing})",
        EXIT_CONFIG_ERROR,
        json_mode,
    )


def _require_module(module_name: str, json_mode: bool) -> Any:
    """Import a parallel EP-018 module, failing closed (exit 2) if absent.

    mypy cannot resolve dynamic string imports, so lazy loading keeps this
    CLI type-safe and bootable even when the parallel module is missing.
    """
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", None) or module_name
        _fail_closed(module_name, missing, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INTERNAL_ERROR, json_mode)


def _require_attr(module: Any, attr_name: str, module_name: str, json_mode: bool) -> Any:
    """Fetch one attribute from a parallel module, failing closed on absence."""
    value = getattr(module, attr_name, None)
    if value is None:
        _fail_closed(module_name, f"{module_name}.{attr_name}", json_mode)
    return value


def _trigger_type_name(trigger_type: Any) -> str:
    """Render a TriggerType enum member as its string value."""
    if hasattr(trigger_type, "value"):
        return str(trigger_type.value)
    return str(trigger_type)


def _state_root(base: str | Path) -> Path:
    """Resolve and create the beacon state directory (lazily, on use)."""
    root = Path(base)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _snapshot_payload(snapshot: Any) -> dict[str, object]:
    """Render a SnapshotRecord as a stable result payload."""
    return {
        "snapshot_id": snapshot.snapshot_id,
        "trigger_id": snapshot.trigger_id,
        "trigger_type": snapshot.trigger_type,
        "summary": snapshot.summary,
    }


def _decision_payload(proposal_id: str, decision: str) -> dict[str, object]:
    """Render a recorded proposal decision as a stable result payload."""
    return {
        "proposal_id": proposal_id,
        "decision": decision,
        "recorded_at": datetime.now(UTC).isoformat(),
    }


@beacon_app.command("run")
def beacon_run_cmd(
    ctx: typer.Context,
    trigger_type: str = typer.Option(
        DEFAULT_TRIGGER_TYPE,
        "--type",
        help="Trigger type name (default: security_advisory).",
    ),
    summary: str = typer.Option(
        DEFAULT_SUMMARY,
        "--summary",
        help="Snapshot summary (default: offline investigation run).",
    ),
    state: str = typer.Option(
        DEFAULT_STATE_DIR,
        "--state",
        help="Beacon state directory (default: .humanhand/beacon).",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output (documented no-op; this module never emits color).",
    ),
) -> None:
    """Start an offline trigger snapshot. Never touches the network."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    state_root = _state_root(state)

    # Parallel surface: types -> snapshot_store. (Evidence is used by
    # `beacon sources`, not by `beacon run`.)
    types_mod = _require_module("humanhand.domain.beacon_types", json_mode)
    store_mod = _require_module("humanhand.infra.beacon.snapshot_store", json_mode)

    # Resolve the TriggerType member by name; unknown names fail closed.
    trigger_enum = _require_attr(
        types_mod, "BeaconTriggerType", "humanhand.domain.beacon_types", json_mode
    )
    try:
        member = trigger_enum[trigger_type.upper()]
    except (KeyError, AttributeError, TypeError):
        _fail_closed(
            "humanhand.domain.beacon_types",
            f"BeaconTriggerType member {trigger_type!r}",
            json_mode,
        )
    trigger_type_name = _trigger_type_name(member)
    create_trigger = _require_attr(
        types_mod, "create_trigger", "humanhand.domain.beacon_types", json_mode
    )
    try:
        trigger = create_trigger(member, summary)
    except DomainError as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    store_cls = _require_attr(
        store_mod, "SnapshotStore", "humanhand.infra.beacon.snapshot_store", json_mode
    )
    store = store_cls(state_root)
    try:
        snapshot = store.store_snapshot(trigger, summary)
    except DomainError as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    except (FileIOError, OSError) as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INTERNAL_ERROR, json_mode)
    _render_json(
        {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "ok",
            "investigation_id": trigger.trigger_id,
            "trigger_type": trigger_type_name,
            "snapshot_id": snapshot.snapshot_id,
        }
    )


@beacon_app.command("report")
def beacon_report_cmd(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="Investigation (trigger) id to read."),
    state: str = typer.Option(
        DEFAULT_STATE_DIR,
        "--state",
        help="Beacon state directory (default: .humanhand/beacon).",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output (documented no-op; this module never emits color).",
    ),
) -> None:
    """List snapshots for one investigation."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    store_mod = _require_module("humanhand.infra.beacon.snapshot_store", json_mode)
    store = _require_attr(
        store_mod, "SnapshotStore", "humanhand.infra.beacon.snapshot_store", json_mode
    )(_state_root(state))
    try:
        snapshots = store.load_snapshots(investigation_id)
    except DomainError as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    except (FileIOError, OSError) as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INTERNAL_ERROR, json_mode)
    _render_json(
        {
            "investigation_id": investigation_id,
            "count": len(snapshots),
            "snapshots": [_snapshot_payload(snapshot) for snapshot in snapshots],
        }
    )


@beacon_app.command("sources")
def beacon_sources_cmd(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(
        ..., help="Investigation (trigger) id to report sources for."
    ),
    state: str = typer.Option(
        DEFAULT_STATE_DIR,
        "--state",
        help="Beacon state directory (default: .humanhand/beacon).",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output (documented no-op; this module never emits color).",
    ),
) -> None:
    """Report the evidence source registry for an investigation."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    registry_mod = _require_module("humanhand.infra.beacon.source_registry", json_mode)
    sources_for_trigger = _require_attr(
        registry_mod,
        "sources_for_trigger",
        "humanhand.infra.beacon.source_registry",
        json_mode,
    )
    store_mod = _require_module("humanhand.infra.beacon.snapshot_store", json_mode)
    store = _require_attr(
        store_mod, "SnapshotStore", "humanhand.infra.beacon.snapshot_store", json_mode
    )(_state_root(state))
    try:
        snapshots = store.load_snapshots(investigation_id)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    if not snapshots:
        _report_error(f"Investigation not stored: {investigation_id}", EXIT_IO_ERROR, json_mode)
    sources = sources_for_trigger(snapshots[0].trigger_type)
    _render_json(
        {
            "investigation_id": investigation_id,
            "count": len(sources),
            "sources": [
                {
                    "source_id": src.name,
                    "tier": src.tier,
                    "label": src.name,
                    "url": src.url,
                }
                for src in sources
            ],
        }
    )


def _load_proposal_for_decision(proposal_id: str, state: str, json_mode: bool) -> tuple[Any, Any]:
    """Load the proposal store and the proposal; fail closed on absence."""
    store_mod = _require_module("humanhand.infra.beacon.proposal_store", json_mode)
    store = _require_attr(
        store_mod, "ProposalStore", "humanhand.infra.beacon.proposal_store", json_mode
    )(_state_root(state))
    try:
        proposal = store.load_proposal(proposal_id)
    except DomainError as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    except (FileIOError, OSError) as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INTERNAL_ERROR, json_mode)
    return store, proposal


def _record_decision(store: Any, proposal_id: str, decision: str, json_mode: bool) -> None:
    """Append a decision record to the proposal store."""
    try:
        store.append_decision(proposal_id, _decision_payload(proposal_id, decision))
    except DomainError as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    except (FileIOError, OSError) as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INTERNAL_ERROR, json_mode)


@beacon_app.command("approve")
def beacon_approve_cmd(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(..., help="Proposal id to approve."),
    state: str = typer.Option(
        DEFAULT_STATE_DIR,
        "--state",
        help="Beacon state directory (default: .humanhand/beacon).",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output (documented no-op; this module never emits color).",
    ),
) -> None:
    """Approve a remediation proposal, unless the firewall blocks it.

    ADR-006: a proposal with ``blocked_action=True`` cannot be approved
    through any ordinary path; this command refuses with exit code 1.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    store, proposal = _load_proposal_for_decision(proposal_id, state, json_mode)
    policy_mod = _require_module("humanhand.domain.beacon_policy", json_mode)
    loader_mod = _require_module("humanhand.infra.beacon.policy_loader", json_mode)
    review = _require_attr(
        policy_mod, "review_proposal", "humanhand.domain.beacon_policy", json_mode
    )
    try:
        current_review = review(
            proposal,
            allowed_actions=loader_mod.load_allowed_actions(),
            blocked_actions=loader_mod.load_blocked_actions(),
        )
    except (DomainError, ValueError) as exc:
        _report_error(message_for_exception(exc), EXIT_CONFIG_ERROR, json_mode)
    if not hasattr(proposal, "blocked_action"):
        _report_error(
            f"proposal {proposal_id} has no blocked_action flag; refusing to approve",
            EXIT_CONFIG_ERROR,
            json_mode,
        )
    if bool(proposal.blocked_action):
        _report_error(
            (
                f"proposal {proposal_id} is blocked by the research beacon firewall "
                "and cannot be approved"
            ),
            EXIT_INPUT_ERROR,
            json_mode,
        )
    if current_review.blocked_action or "decision=allow" not in current_review.policy_note:
        _report_error(
            f"proposal {proposal_id} was not allowed by policy review",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    _record_decision(store, proposal_id, "approve", json_mode)
    _render_json(
        {
            "proposal_id": proposal_id,
            "decision": "approve",
            "blocked_action": False,
            "status": "ok",
        }
    )


@beacon_app.command("deny")
def beacon_deny_cmd(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(..., help="Proposal id to deny."),
    state: str = typer.Option(
        DEFAULT_STATE_DIR,
        "--state",
        help="Beacon state directory (default: .humanhand/beacon).",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output (documented no-op; this module never emits color).",
    ),
) -> None:
    """Deny a remediation proposal. Denial is always allowed."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    store, proposal = _load_proposal_for_decision(proposal_id, state, json_mode)
    _record_decision(store, proposal_id, "deny", json_mode)
    _render_json(
        {
            "proposal_id": proposal_id,
            "decision": "deny",
            "blocked_action": bool(getattr(proposal, "blocked_action", False)),
            "status": "ok",
        }
    )
