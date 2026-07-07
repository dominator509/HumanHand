"""Regression tests for the loop gate shell contract."""

from __future__ import annotations

import stat
import subprocess
import tempfile
from pathlib import Path


def _write_script(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _copy_loop_script(repo_root: Path, tmp_repo: Path) -> Path:
    scripts_dir = tmp_repo / "scripts"
    scripts_dir.mkdir()

    loop_script = repo_root / "scripts" / "loop.sh"
    _write_script(
        scripts_dir / "loop.sh",
        loop_script.read_text(encoding="utf-8"),
    )
    return scripts_dir


class TestLoopScript:
    def test_success_only_prints_build_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            scripts_dir = _copy_loop_script(Path.cwd(), tmp_repo)
            _write_script(
                scripts_dir / "production-readiness-check.sh",
                "#!/usr/bin/env sh\n"
                "set -eu\n"
                "printf 'hidden stdout\\n'\n"
                "printf 'hidden stderr\\n' >&2\n",
            )

            result = subprocess.run(
                ["sh", "scripts/loop.sh"],
                capture_output=True,
                cwd=tmp_repo,
                encoding="utf-8",
                check=False,
            )

        assert result.returncode == 0
        assert result.stdout == "build: complete\n"
        assert result.stderr == ""

    def test_failure_replays_captured_output_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            scripts_dir = _copy_loop_script(Path.cwd(), tmp_repo)
            _write_script(
                scripts_dir / "production-readiness-check.sh",
                "#!/usr/bin/env sh\n"
                "set -eu\n"
                "printf 'failure stdout\\n'\n"
                "printf 'failure stderr\\n' >&2\n"
                "exit 1\n",
            )

            result = subprocess.run(
                ["sh", "scripts/loop.sh"],
                capture_output=True,
                cwd=tmp_repo,
                encoding="utf-8",
                check=False,
            )

        assert result.returncode == 1
        assert result.stdout == ""
        assert "failure stdout\n" in result.stderr
        assert "failure stderr\n" in result.stderr
