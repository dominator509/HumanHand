"""Integration tests for the file-backed Style Fidelity Vault."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanhand.infra.stores.style_vault import StyleVault, StyleVaultError


@pytest.fixture
def vault(tmp_path: Path) -> StyleVault:
    return StyleVault(tmp_path / "vault")


class TestStyleVaultOriginals:
    def test_store_and_load_with_integrity(self, vault: StyleVault) -> None:
        raw = b"original style sample bytes"
        artifact_id = vault.store_original(raw)
        assert len(artifact_id) == 64
        assert vault.original_exists(artifact_id)
        assert vault.load_original(artifact_id) == raw

    def test_idempotent_store(self, vault: StyleVault) -> None:
        raw = b"same bytes"
        first = vault.store_original(raw)
        second = vault.store_original(raw)
        assert first == second

    def test_integrity_violation_detected(self, vault: StyleVault, tmp_path: Path) -> None:
        raw = b"integrity test bytes"
        artifact_id = vault.store_original(raw)
        # Corrupt the stored file on disk (simulating tampering).
        originals = tmp_path / "vault" / "originals"
        (originals / f"{artifact_id}.bin").write_bytes(b"tampered!")
        with pytest.raises(StyleVaultError, match="integrity"):
            vault.load_original(artifact_id)

    def test_missing_original_raises(self, vault: StyleVault) -> None:
        with pytest.raises(StyleVaultError, match="not stored"):
            vault.load_original("0" * 64)


class TestStyleVaultPackages:
    def test_store_and_load_package(self, vault: StyleVault) -> None:
        package_json = b'{"schema": "style-evidence-package"}'
        vault.store_package("sty-000000000000000000000001", package_json)
        assert vault.load_package("sty-000000000000000000000001") == package_json
        assert "sty-000000000000000000000001" in vault.list_packages()

    def test_write_once_collision_rejected(self, vault: StyleVault) -> None:
        vault.store_package("sty-000000000000000000000001", b'{"v": 1}')
        with pytest.raises(StyleVaultError, match="collision"):
            vault.store_package("sty-000000000000000000000001", b'{"v": 2}')

    def test_list_sorted(self, vault: StyleVault) -> None:
        vault.store_package("sty-000000000000000000000002", b"{}")
        vault.store_package("sty-000000000000000000000001", b"{}")
        assert vault.list_packages() == (
            "sty-000000000000000000000001",
            "sty-000000000000000000000002",
        )


class TestStyleVaultIdValidation:
    def test_path_traversal_id_rejected(self, vault: StyleVault) -> None:
        with pytest.raises(StyleVaultError, match="Invalid package id"):
            vault.load_package("../../outside")

    def test_malformed_id_rejected(self, vault: StyleVault) -> None:
        with pytest.raises(StyleVaultError, match="Invalid package id"):
            vault.store_package("sty-not-hex", b"{}")

    def test_original_exists_rejects_path_traversal(self, vault: StyleVault) -> None:
        with pytest.raises(StyleVaultError, match="Invalid artifact id"):
            vault.original_exists("../outside")


class TestStyleVaultDecisions:
    def test_append_only_log(self, vault: StyleVault) -> None:
        vault.append_decision({"package_id": "p1", "span_id": "a1"})
        vault.append_decision({"package_id": "p1", "span_id": "a2"})
        decisions = vault.read_decisions()
        assert len(decisions) == 2
        assert decisions[0]["span_id"] == "a1"
        assert decisions[1]["span_id"] == "a2"

    def test_corrupt_decision_line_fails_closed(self, vault: StyleVault, tmp_path: Path) -> None:
        vault.append_decision({"package_id": "p1", "span_id": "a1"})
        with (tmp_path / "vault" / "decisions.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("not json at all\n")
        with pytest.raises(StyleVaultError, match="Corrupt"):
            vault.read_decisions()
