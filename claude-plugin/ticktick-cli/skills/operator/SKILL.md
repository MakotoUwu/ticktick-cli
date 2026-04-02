---
name: operator
description: Use the ticktick CLI to inspect tasks, projects, habits, focus state, and calendar entries, and to safely stage or execute TickTick actions in Claude Code.
---

# TickTick Operator

Use the installed `ticktick` CLI as the primary interface to TickTick.

## First step

Always start with:

```bash
ticktick auth status
```

If not authenticated, stop and tell the user to authenticate themselves. Never handle passwords or tokens directly.

## Defaults

- Prefer `--output json` for machine-readable responses.
- Use `ticktick schema` and `ticktick <command> --help` when you need to discover command structure.
- Prefer read-only commands first when exploring account state.
- Use `--dry-run` before proposing or previewing any mutating operation.

## Safe read-only commands

```bash
ticktick --output json task list --limit 20
ticktick --output json task today
ticktick --output json task overdue
ticktick --output json task search "QUERY"
ticktick --output json project list
ticktick --output json habit list
ticktick --output json focus status
ticktick --output json calendar event list --limit 10
ticktick --output json sync
```

## Mutation policy

Ask before mutating the user's TickTick account:

- task creation or edits
- project or tag creation
- habit check-ins or edits
- focus start or stop
- any delete operation

For destructive actions, require an explicit confirmation and use the CLI's `--yes` flags where supported.

## Important product semantics

- External and subscribed calendar events are read-only mirrors.
- TickTick-owned calendar entries expose `linkedTaskId` and should be mutated through task commands, not calendar commands.
- `focus link` is intentionally not treated as reliable live relinking. If a running focus session must be tied to a task, use a safer stop/start flow.

## Natural language dates

The CLI accepts natural language date input:

```bash
ticktick --dry-run --output json task add "Review PR" --due tomorrow
ticktick --dry-run --output json task add "Plan sprint" --due "next monday"
```

## Response style

- Return IDs for created or resolved resources whenever possible.
- Be explicit about whether the action was read-only, dry-run, or a real mutation.
- If live behavior differs from docs or assumptions, trust the CLI output and say what you observed.
