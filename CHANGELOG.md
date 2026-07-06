# Changelog

All notable changes to Human Hand are documented in this file.

## [Unreleased]

### Added
- Foundation package structure with `pyproject.toml` and uv dependency management.
- Source skeleton: `src/humanhand/` with CLI (`cli/`) and infra (`infra/`) packages.
- Typer CLI application with `--help`, `--version`, and `health` commands.
- Configuration dataclass with environment variable loading and validation.
- Baseline unit tests (8 tests), E2E CLI tests (6 tests), and smoke tests (3 tests).
- CI workflow for Windows and Ubuntu with Python 3.11.
- Ruff lint/format, mypy strict typechecking, pytest, bandit, and pip-audit tooling.
- Build pipeline producing wheel and sdist artifacts.
- Documentation baseline: README, CHANGELOG, ARCHITECTURE, and environment docs.

## [0.1.0] — Unreleased
