"""Parser worker environment and policy contract.

The worker process must never load network, model, config, or cache code;
``verify_worker_environment`` is the real enforcement for that rule.
"""

from __future__ import annotations

import sys
from dataclasses import fields
from typing import Any, get_type_hints

from humanhand.domain.import_policy import ImportPolicy, validate_policy
from humanhand.domain.types import DomainError
from humanhand.domain.unicode_policy import UnicodePolicy

FORBIDDEN_MODULE_PREFIXES: tuple[str, ...] = (
    "humanhand.infra.http",
    "humanhand.infra.llm",
    "humanhand.infra.cache",
    "humanhand.infra.config",
    "httpx",
    "openai",
    "requests",
)

_POLICY_FIELD_TYPES: dict[str, Any] = get_type_hints(ImportPolicy)
_UNICODE_FIELD_TYPES: dict[str, Any] = get_type_hints(UnicodePolicy)


def install_network_guard() -> None:
    """Deny socket and DNS activity for the lifetime of the worker process.

    Pydantic imports parts of :mod:`socket` transitively, so checking loaded
    module names cannot by itself enforce the worker's deny-network policy.
    Python audit hooks are process-local and cannot be removed, which makes
    them appropriate for the short-lived parser worker.
    """

    def deny_socket_event(event: str, _args: tuple[object, ...]) -> None:
        if event.startswith("socket."):
            raise PermissionError("parser worker network access is denied")

    sys.addaudithook(deny_socket_event)


def verify_worker_environment() -> list[str]:
    """Return sorted names of loaded modules that violate the worker sandbox.

    Scans ``sys.modules`` and reports every loaded module whose name starts
    with a forbidden prefix. Over-inclusion is safe: the worker fails
    closed whenever any such module is present.

    The stdlib ``socket`` and ``urllib`` modules are deliberately absent
    from the prefix list: importing pydantic (required by the wire
    protocol) transitively loads them via ``importlib.metadata`` ->
    ``email.utils`` for version detection, so they are always present and
    never used for I/O. The list still covers every HumanHand network,
    model, config, and cache module plus direct HTTP client libraries.
    """
    return sorted(
        name
        for name in sys.modules
        if any(name.startswith(prefix) for prefix in FORBIDDEN_MODULE_PREFIXES)
    )


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, got bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{name} must be an integer, got {value!r}")
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"{name} must be an integer, got {type(value).__name__}")


def _as_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, got bool")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValueError(f"{name} must be a number, got {type(value).__name__}")


def _coerce_field(value: object, expected: type[Any], name: str) -> Any:
    """Coerce one policy field value, raising ValueError on bad input."""
    if expected is int:
        return _as_int(value, name)
    if expected is float:
        return _as_float(value, name)
    if expected is str:
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string, got {type(value).__name__}")
        return value
    if expected is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be a boolean, got {type(value).__name__}")
        return value
    raise ValueError(f"{name} has unsupported field type {expected}")


def _unicode_policy_from_dict(raw: dict[str, object]) -> UnicodePolicy:
    unknown = set(raw) - set(_UNICODE_FIELD_TYPES)
    if unknown:
        raise ValueError(f"Unknown unicode policy fields: {', '.join(sorted(unknown))}")
    kwargs: dict[str, Any] = {}
    for field in fields(UnicodePolicy):
        if field.name in raw:
            kwargs[field.name] = _coerce_field(
                raw[field.name], _UNICODE_FIELD_TYPES[field.name], field.name
            )
    return UnicodePolicy(**kwargs)


def policy_from_dict(raw: dict[str, object]) -> ImportPolicy:
    """Build an ImportPolicy from a plain dict, failing closed on unknowns.

    Keys must be ImportPolicy field names; missing keys take the dataclass
    defaults. Numeric fields are coerced from ints, floats, or numeric
    strings. Unknown keys, wrong value types, and invalid policy values
    raise ValueError.
    """
    unknown = set(raw) - set(_POLICY_FIELD_TYPES)
    if unknown:
        raise ValueError(f"Unknown policy fields: {', '.join(sorted(unknown))}")
    kwargs: dict[str, Any] = {}
    for field in fields(ImportPolicy):
        if field.name == "unicode":
            if "unicode" not in raw:
                kwargs["unicode"] = UnicodePolicy()
                continue
            unicode_raw = raw["unicode"]
            if not isinstance(unicode_raw, dict):
                raise ValueError("unicode policy must be an object")
            kwargs["unicode"] = _unicode_policy_from_dict(unicode_raw)
            continue
        if field.name in raw:
            kwargs[field.name] = _coerce_field(
                raw[field.name], _POLICY_FIELD_TYPES[field.name], field.name
            )
    try:
        policy = ImportPolicy(**kwargs)
    except TypeError as exc:
        raise ValueError(f"Invalid import policy: {exc}") from exc
    try:
        validate_policy(policy)
    except DomainError as exc:
        raise ValueError(f"Invalid import policy: {exc}") from exc
    return policy
