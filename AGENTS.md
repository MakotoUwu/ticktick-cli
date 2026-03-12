# AGENTS.md — ticktick-cli

Agent-native CLI for TickTick. JSON output by default, no interactive prompts.

## Discovery

```bash
ticktick schema                           # Full CLI structure (commands, flags, types)
ticktick --help                           # Top-level help
ticktick <command> --help                 # Command-specific help
```

## Commands

### Check auth (always run first)

```bash
ticktick auth status
```

If not authenticated, **ask the user** to run auth commands themselves — never handle passwords.

### Tasks

```bash
ticktick task list [--limit N] [--priority high|medium|low|none] [--project PROJECT_ID] [--tag TAG] [--sort due|priority|title]
ticktick task today
ticktick task overdue
ticktick task search "QUERY"
ticktick task show TASK_ID
ticktick task add "TITLE" [--priority high|medium|low] [--project PROJECT_ID] [--due DATE] [--tag TAG]
ticktick task edit TASK_ID [--title "NEW"] [--priority LEVEL]
ticktick task done TASK_ID [TASK_ID...]
ticktick task abandon TASK_ID [TASK_ID...]
ticktick task delete TASK_ID --yes
ticktick task move TASK_ID --to PROJECT_ID
ticktick task completed [--from DATE] [--to DATE] [--limit N]
ticktick task trash [--limit N]
ticktick task pin TASK_ID
ticktick task unpin TASK_ID
ticktick task batch-add --file tasks.json
```

### Subtasks

```bash
ticktick subtask set TASK_ID --parent PARENT_ID
ticktick subtask unset TASK_ID --parent PARENT_ID
ticktick subtask list PARENT_TASK_ID
```

### Projects

```bash
ticktick project list
ticktick project create "NAME" [--color "#HEX"]
ticktick project show PROJECT_ID
ticktick project edit PROJECT_ID [--name "NEW"]
ticktick project delete PROJECT_ID --yes
```

### Folders

```bash
ticktick folder list
ticktick folder create "NAME"
ticktick folder rename FOLDER_ID "NEW_NAME"
ticktick folder delete FOLDER_ID --yes
```

### Habits

```bash
ticktick habit list [--include-archived]
ticktick habit show HABIT_ID
ticktick habit create "NAME" [--type boolean|numeric] [--goal N]
ticktick habit edit HABIT_ID [--name N] [--goal N]
ticktick habit delete HABIT_ID --yes
ticktick habit checkin HABIT_ID [--date YYYYMMDD] [--value N]
ticktick habit history HABIT_ID [--days N]
ticktick habit archive HABIT_ID
ticktick habit unarchive HABIT_ID
```

### Tags

```bash
ticktick tag list
ticktick tag create "NAME" [--color "#HEX"]
ticktick tag edit "NAME" [--label "NEW"] [--color "#HEX"]
ticktick tag rename "OLD" "NEW"
ticktick tag merge "SOURCE" "TARGET"
ticktick tag delete "NAME" --yes
```

### Kanban Columns

```bash
ticktick column list PROJECT_ID
ticktick column create PROJECT_ID "NAME"
ticktick column edit COLUMN_ID --project PROJECT_ID [--name "NEW"]
ticktick column delete COLUMN_ID --project PROJECT_ID --yes
```

### Focus / Pomodoro

```bash
ticktick focus start [--duration 25] [--note "deep work"]     # Start timer
ticktick focus stop [--save/--no-save]                         # Stop timer
ticktick focus status                                          # Current timer state
ticktick focus log --start HH:MM --end HH:MM [--note "note"]  # Log past session
ticktick focus delete POMODORO_ID                              # Delete record
ticktick focus stats                                           # Today/total counts
ticktick focus heatmap [--days N]                              # Daily focus heatmap
ticktick focus by-tag [--days N]                               # Focus time by tag
```

### User & Sync

```bash
ticktick user profile
ticktick user status
ticktick user stats
ticktick user preferences
ticktick sync                              # Full account state dump
```

### Config

```bash
ticktick config list
ticktick config get KEY
ticktick config set KEY VALUE
ticktick config path
```

## Global Options

All global flags go **before** the command:

```bash
ticktick [--human] [--output json|csv|yaml] [--fields FIELDS] [--dry-run] [--verbose] [--profile NAME] COMMAND
```

| Flag | Description |
|------|-------------|
| `--human` | Rich table output instead of JSON |
| `--output FORMAT` | `json` (default), `csv`, `yaml` |
| `--fields FIELDS` | Comma-separated field list: `--fields id,title,priority` |
| `--dry-run` | Preview actions without making API calls |
| `--verbose` | Debug output |
| `--profile NAME` | Auth profile (default: `default`) |

## Output Contract

All commands return:

```
Success:  {"ok": true, "data": [...], "count": N}
Message:  {"ok": true, "message": "Task created."}
Error:    {"ok": false, "error": "description"}
```

Exit codes: `0` success, `1` error, `2` auth error.

## Natural Language Dates

Date flags accept natural language:

```bash
ticktick task add "Meeting" --due tomorrow
ticktick task add "Report" --due "next monday"
ticktick task add "Review" --due "in 3 days"
ticktick task list --due this-week
```

## Boundaries

### Always safe

- Any read command (`list`, `show`, `search`, `today`, `overdue`, `status`, `sync`, `stats`, `heatmap`)
- `ticktick config list` / `ticktick config path`
- `ticktick schema`
- `ticktick focus status`

### Ask user first

- Creating tasks, projects, tags, habits (`add`, `create`)
- Editing or moving tasks (`edit`, `move`)
- Checking in habits (`checkin`)
- Starting/stopping focus timer (`focus start`, `focus stop`)
- Logging focus records (`focus log`)

### Never do without explicit confirmation

- Any delete operation — always use `--yes` flag
- Auth commands — user must run these themselves
- Batch operations (`batch-add`) with user data

## Conventions

- Task IDs are 24-character hex strings (MongoDB ObjectId format)
- Dates in API responses are ISO 8601 with timezone offset
- V2 commands (habits, focus, tags, folders, columns) require V2 authentication
- Use `jq` for complex JSON parsing: `ticktick task list | jq '.data[].title'`

## Tech Stack

- Python 3.10+, Click framework, httpx, Rich, Pydantic v2
- Config: `~/.config/ticktick-cli/<profile>/`
- Dual API: V1 (OAuth2, official) + V2 (session, full-feature)
- 245 tests, CI via GitHub Actions

## Build & Test

```bash
pip install -e ".[dev]"
pytest -v               # 245 tests
```
