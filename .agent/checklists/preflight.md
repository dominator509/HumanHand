# Preflight Checklist

Run before editing.

- [ ] Repository root contains `AGENTS.md`.
- [ ] Repository root contains `COMMANDS.md`.
- [ ] Repository root contains `.agent/PLANS.md`.
- [ ] Repository root contains active ExecPlan.
- [ ] `sh scripts/preflight.sh` prints `preflight: ok`.
- [ ] `git status --short` reviewed.
- [ ] uv availability checked.
- [ ] Python 3.11 availability checked after EP-001.
- [ ] Required secrets checked only for live paths; local tests need no secrets.
- [ ] `.env` is ignored if present.
- [ ] No local service is required unless active ExecPlan explicitly says so.
- [ ] Known blockers are recorded in the active ExecPlan.
