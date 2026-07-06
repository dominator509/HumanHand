"""Verify domain layer does not import forbidden modules."""

import importlib
import pkgutil
from pathlib import Path

FORBIDDEN_MODULES = {
    "typer",
    "httpx",
    "openai",
    "sqlite3",
    "logging",
    "pathlib",
    "humanhand.cli",
    "humanhand.infra",
    "humanhand.application",
}

FORBIDDEN_PATTERNS = {
    "network",
    "http",
    "cache",
    "log",
}


def _get_domain_modules() -> list[str]:
    """Discover all domain module names."""
    import humanhand.domain

    package_dir = Path(humanhand.domain.__file__).parent
    modules = ["humanhand.domain"]

    for _importer, name, is_pkg in pkgutil.iter_modules([str(package_dir)]):
        full_name = f"humanhand.domain.{name}"
        modules.append(full_name)
        if is_pkg:
            sub_dir = package_dir / name
            for _sub_importer, sub_name, _unused in pkgutil.iter_modules([str(sub_dir)]):
                modules.append(f"{full_name}.{sub_name}")

    return modules


class TestDomainImportBoundaries:
    """Domain must not import CLI, infra, network, cache, or logging modules."""

    def test_no_forbidden_imports(self) -> None:
        """Verify no domain module imports forbidden modules."""
        violations: list[str] = []

        for module_name in _get_domain_modules():
            try:
                mod = importlib.import_module(module_name)
            except ImportError:
                continue

            for attr_name in dir(mod):
                if attr_name.startswith("_"):
                    continue
                obj = getattr(mod, attr_name)
                if hasattr(obj, "__module__"):
                    obj_module = obj.__module__
                    for forbidden in FORBIDDEN_MODULES:
                        if obj_module == forbidden or obj_module.startswith(forbidden + "."):
                            violations.append(
                                f"{module_name} imports {obj_module} (via {attr_name})"
                            )

        if violations:
            msg = "Domain imports forbidden modules:\n" + "\n".join(violations)
            raise AssertionError(msg)

    def test_no_direct_forbidden_imports_in_source(self) -> None:
        """Scan domain source files for forbidden import statements."""
        import humanhand.domain

        package_dir = Path(humanhand.domain.__file__).parent
        violations: list[str] = []

        for py_file in package_dir.rglob("*.py"):
            if py_file.name == "__init__.py" and py_file.parent == package_dir:
                continue  # Allow __init__.py re-exports
            content = py_file.read_text()
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    for forbidden in FORBIDDEN_MODULES:
                        if forbidden in stripped:
                            violations.append(f"{py_file.name}: {stripped}")

        if violations:
            msg = "Domain source files import forbidden modules:\n" + "\n".join(violations)
            raise AssertionError(msg)
