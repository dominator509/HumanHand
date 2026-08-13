# ADR-004: Controlled Parser Worker Processes

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

Complex document parsing may use short-lived child processes with bounded time,
memory, expanded-size, node-count, and archive-depth limits. HumanHand remains a
CLI-only application with no daemon.

## Reason

Malformed or hostile containers must not compromise the main process or permit parser
network access, active-content execution, or unbounded resource use.

## Consequence

The worker protocol is explicit and testable. Parser failures become findings and
fail-closed import results rather than silent best-effort parsing.
