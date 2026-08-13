"""Append-only research proposal store for the Research Beacon.

Records are written to ``proposals.jsonl`` (one JSON object per physical
line, newest last) using the same serialization as the style vault decision
log: sorted keys, compact separators, UTF-8, LF newlines. Proposal ids are
``prp-<24 hex>``; malformed records are rejected, never silently skipped.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from humanhand.domain.beacon_proposals import (
    BeaconProposal,
    proposal_from_payload,
    proposal_to_payload,
)
from humanhand.domain.types import DomainError


class ProposalStoreError(DomainError):
    """Raised when proposal log invariants are violated."""

    pass


_PROPOSAL_ID_RE = re.compile(r"^prp-[0-9a-f]{24}$")
_DOMAIN_PROPOSAL_ID_RE = re.compile(r"^prop-[0-9a-f]{24}$")


class ProposalStore:
    """Local, append-only research proposal log."""

    def __init__(self, store_dir: str | Path) -> None:
        self._root = Path(store_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._log = self._root / "proposals.jsonl"

    @property
    def root(self) -> Path:
        return self._root

    def append_proposal(self, record: dict[str, object]) -> None:
        """Append one proposal record; the log is append-only."""
        proposal_id = record.get("id")
        if not isinstance(proposal_id, str):
            raise ProposalStoreError("Proposal record missing id")
        if _PROPOSAL_ID_RE.match(proposal_id) is None:
            raise ProposalStoreError(f"Invalid proposal id: {proposal_id!r}")
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self._log.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)

    def load_proposals(self) -> tuple[dict[str, object], ...]:
        """Return proposal records in log order (oldest first)."""
        if not self._log.exists():
            return ()
        proposals: list[dict[str, object]] = []
        for line in self._log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise ProposalStoreError("Corrupt proposal log line") from None
            if not isinstance(record, dict):
                raise ProposalStoreError("Corrupt proposal log record")
            proposal_id = record.get("id")
            if not isinstance(proposal_id, str) or _PROPOSAL_ID_RE.match(proposal_id) is None:
                raise ProposalStoreError("Proposal log record has invalid id")
            proposals.append(record)
        return tuple(proposals)

    def list_proposal_ids(self) -> tuple[str, ...]:
        """Return proposal ids in log order (oldest first)."""
        return tuple(str(record["id"]) for record in self.load_proposals())

    def store_proposal(self, proposal: BeaconProposal) -> None:
        """Persist one schema-validated domain proposal without replacement."""
        proposals_dir = self._root / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        path = proposals_dir / f"{proposal.proposal_id}.json"
        data = (
            json.dumps(proposal_to_payload(proposal), sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        if path.exists():
            if path.read_bytes() != data:
                raise ProposalStoreError(f"Proposal id collision: {proposal.proposal_id}")
            return
        descriptor, temporary_name = tempfile.mkstemp(dir=proposals_dir, suffix=".tmp")
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise ProposalStoreError(
                        f"Proposal id collision: {proposal.proposal_id}"
                    ) from None
        finally:
            temporary.unlink(missing_ok=True)

    def load_proposal(self, proposal_id: str) -> BeaconProposal:
        """Load and strictly validate a stored domain proposal."""
        if _DOMAIN_PROPOSAL_ID_RE.fullmatch(proposal_id) is None:
            raise ProposalStoreError(f"Invalid proposal id: {proposal_id!r}")
        path = self._root / "proposals" / f"{proposal_id}.json"
        if not path.is_file():
            raise ProposalStoreError(f"Proposal not stored: {proposal_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProposalStoreError(f"Corrupt proposal: {proposal_id}") from exc
        if not isinstance(payload, dict):
            raise ProposalStoreError(f"Corrupt proposal: {proposal_id}")
        try:
            proposal = proposal_from_payload(payload)
        except Exception as exc:
            raise ProposalStoreError(f"Invalid proposal payload: {proposal_id}") from exc
        if proposal.proposal_id != proposal_id:
            raise ProposalStoreError(f"Proposal id mismatch: {proposal_id}")
        return proposal

    def append_decision(self, proposal_id: str, decision: dict[str, object]) -> None:
        """Append a human decision after validating its proposal and shape."""
        self.load_proposal(proposal_id)
        if decision.get("proposal_id") != proposal_id:
            raise ProposalStoreError("Decision proposal id mismatch")
        if decision.get("decision") not in {"approve", "deny"}:
            raise ProposalStoreError("Invalid proposal decision")
        line = json.dumps(decision, sort_keys=True, separators=(",", ":")) + "\n"
        with (self._root / "decisions.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
