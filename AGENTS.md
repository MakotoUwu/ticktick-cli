# AGENTS.md — ticktick-cli

Agent-native CLI for TickTick. JSON output by default, no interactive prompts.

## Commands

### Check auth (always run first)

```bash
ticktick auth status
```

If not authenticated, **ask the user** to run auth commands themselves — never handle passwords.

### Tasks

```bash
ticktick task list [--limit N] [--priority high|medium|low|none] [--project PROJECT_ID] [--tag TAG]
ticktick task today
ticktick task overdue
ticktick task search "QUERY"
ticktick task show TASK_ID
ticktick task add "TITLE" [--priority high|medium|low] [--project PROJECT_ID] [--due DATE] [--tag TAG]
ticktick task edit TASK_ID [--title "NEW"] [--priority LEVEL]
ticktick task done TASK_ID
ticktick task delete TASK_ID --yes
ticktick task move TASK_ID --to PROJECT_ID
ticktick task completed [--limit N]
```

### Projects

```bash
ticktick project list
ticktick project create "NAME" [--color "#HEX"]
ticktick project show PROJECT_ID
ticktick project delete PROJECT_ID --yes
```

### Habits

```bash
ticktick habit list
ticktick habit checkin HABIT_ID [--date YYYYMMDD] [--value N]
ticktick habit history HABIT_ID [--days N]
```

### Tags

```bash
ticktick tag list
ticktick tag create "NAME"
ticktick tag rename "OLD" "NEW"
ticktick tag delete "NAME" --yes
```

### Focus / Pomodoro

```bash
ticktick focus heatmap [--days N]
ticktick focus by-tag [--days N]
```

### User & Sync

```bash
ticktick user profile
ticktick user stats
ticktick sync                          # Full account state dump
ticktick folder list
ticktick column list PROJECT_ID
```

## Output Contract

All commands return:

```
Success:  {"ok": true, "data": [...], "count": N}
Message:  {"ok": true, "message": "Task created."}
Error:    {"ok": false, "error": "description"}
```

Exit codes: `0` success, `1` error, `2` auth error.

## Boundaries

### Always safe

- Any read command (`list`, `show`, `search`, `today`, `overdue`, `status`, `sync`)
- `ticktick config list` / `ticktick config path`

### Ask user first

- Creating tasks, projects, tags, habits (`add`, `create`)
- Editing or moving tasks (`edit`, `move`)
- Checking in habits (`checkin`)

### Never do without explicit confirmation

- Any delete operation — always use `--yes` flag
- Auth commands — user must run these themselves
- Batch operations (`batch-add`) with user data

## Conventions

- `--human` is a **global option** — goes BEFORE the command: `ticktick --human task list`
- Task IDs are 24-character hex strings (MongoDB ObjectId format)
- Dates in API responses are ISO 8601 with timezone offset
- V2 commands (habits, focus, tags, folders, columns) require V2 authentication
- Use `jq` for complex JSON parsing: `ticktick task list | jq '.data[].title'`

## Tech Stack

- Python 3.10+, Click framework, httpx, Rich
- Config: `~/.config/ticktick-cli/<profile>/`
- Dual API: V1 (OAuth2, official) + V2 (session, unofficial full-feature)

## Build & Test

```bash
pip install -e ".[dev]"
pytest -v               # 115 tests
```
