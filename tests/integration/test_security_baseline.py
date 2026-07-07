"""Integration tests for security baseline: no auth, .env ignored, redaction."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# M1 — Confirm auth is absent
# ---------------------------------------------------------------------------

FORBIDDEN_AUTH_MODULES = [
    "humanhand.auth",
    "humanhand.login",
    "humanhand.session",
    "humanhand.account",
    "humanhand.user",
    "humanhand.role",
    "humanhand.permission",
]

FORBIDDEN_AUTH_CLASS_NAMES = {
    "AuthService",
    "UserSession",
    "LoginHandler",
    "AccountManager",
    "SessionStore",
    "RoleManager",
    "PermissionCheck",
    "TokenIssuer",
    "PasswordReset",
    "SignUpHandler",
}


def _collect_src_python_files() -> list[Path]:
    """Return all .py files under src/humanhand."""
    src_root = Path("src/humanhand")
    if not src_root.exists():
        return []
    return sorted(src_root.rglob("*.py"))


class TestAuthAbsence:
    """Confirm that no authentication, session, or account code exists."""

    def test_no_auth_modules_importable(self) -> None:
        """None of the forbidden auth modules should be importable."""
        for module_name in FORBIDDEN_AUTH_MODULES:
            try:
                __import__(module_name)
                pytest.fail(f"Forbidden auth module is importable: {module_name}")
            except ImportError:
                pass  # Expected — module does not exist

    def test_no_auth_classes_in_source(self) -> None:
        """No class with auth-related names should exist anywhere in src/."""
        for py_file in _collect_src_python_files():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    assert node.name not in FORBIDDEN_AUTH_CLASS_NAMES, (
                        f"Forbidden auth class '{node.name}' found in {py_file}"
                    )

    def test_no_auth_cli_commands(self) -> None:
        """CLI must not expose login/logout/signup/session commands."""
        cli_files = list(Path("src/humanhand").rglob("cli*.py"))
        for cli_file in cli_files:
            text = cli_file.read_text(encoding="utf-8").lower()
            for forbidden in ("def login", "def logout", "def signup", "def session"):
                assert forbidden not in text, (
                    f"Forbidden CLI command '{forbidden}' found in {cli_file}"
                )

    def test_no_account_or_user_table(self) -> None:
        """No source file should define account or user database tables."""
        for py_file in _collect_src_python_files():
            text = py_file.read_text(encoding="utf-8").lower()
            forbidden_table_ddl = (
                "create table users",
                "create table accounts",
                "create table sessions",
            )
            for forbidden in forbidden_table_ddl:
                assert forbidden not in text, f"Forbidden table DDL found in {py_file}: {forbidden}"


# ---------------------------------------------------------------------------
# M1 — Confirm .env is ignored
# ---------------------------------------------------------------------------


class TestDotEnvIgnored:
    """Ensure .env and .env.* patterns are git-ignored."""

    def test_dotenv_in_gitignore(self) -> None:
        """The .gitignore file must contain patterns for .env files."""
        gitignore = Path(".gitignore")
        assert gitignore.exists(), ".gitignore file not found"
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        stripped = {line.strip() for line in lines if line.strip() and not line.startswith("#")}
        assert ".env" in stripped, ".env is not in .gitignore"
        assert ".env.*" in stripped, ".env.* is not in .gitignore"

    def test_no_dotenv_loader(self) -> None:
        """No code should auto-load .env files (python-dotenv, etc.)."""
        for py_file in _collect_src_python_files():
            text = py_file.read_text(encoding="utf-8").lower()
            assert "load_dotenv" not in text, f"dotenv loader found in {py_file}"
            assert "dotenv_values" not in text, f"dotenv_values found in {py_file}"

    def test_secrets_from_env_only(self) -> None:
        """API keys and secrets must be read from environment variables only."""
        # Files that contain redaction patterns (not actual secrets)
        redaction_files = {"logging.py", "test_redaction.py"}
        for py_file in _collect_src_python_files():
            if py_file.name in redaction_files:
                continue  # These files define redaction patterns, not secrets
            text = py_file.read_text(encoding="utf-8")
            # Check no hardcoded secrets in source
            for pattern in ('"sk-', "'sk-", '"ghp_', "'ghp_"):
                assert pattern not in text, f"Possible hardcoded secret key pattern in {py_file}"


# ---------------------------------------------------------------------------
# M2 — Redaction safety (integration-level checks)
# ---------------------------------------------------------------------------


class TestRedactionIntegration:
    """Integration-level checks that redaction covers key scenarios."""

    def test_api_key_not_in_exception_messages(self) -> None:
        """API keys read from env must not appear in any error message format strings."""
        for py_file in _collect_src_python_files():
            text = py_file.read_text(encoding="utf-8")
            # Look for f-strings or .format() that include api_key directly
            if "llm_api_key" in text or "api_key" in text:
                # Verify error classes in these files don't embed the key
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Raise):
                        for child in ast.walk(node):
                            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                                msg = child.value
                                assert "api_key" not in msg.lower(), (
                                    f"Raise message may leak key name in {py_file}: {msg[:80]}"
                                )
