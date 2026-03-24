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
ticktick task duplicate TASK_ID
ticktick task convert TASK_ID --to note|task
ticktick task activity TASK_ID [--limit N]
ticktick task comment list TASK_ID
ticktick task comment add TASK_ID "TEXT"
ticktick task comment delete TASK_ID COMMENT_ID --yes
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
ticktick focus start [--duration 25] [--note "deep work"] [--task TASK_ID]  # Start timer
ticktick focus stop [--save/--no-save]                         # Stop timer
ticktick focus status                                          # Current timer state
ticktick focus log --start HH:MM --end HH:MM [--note "note"]  # Log past session
ticktick focus delete POMODORO_ID                              # Delete record
ticktick focus stats                                           # Today/total counts
ticktick focus heatmap [--days N]                              # Daily focus heatmap
ticktick focus by-tag [--days N]                               # Focus time by tag
```

### Calendar

```bash
ticktick calendar account list
ticktick calendar subscription list
ticktick calendar event list [--calendar-id CALENDAR_ID] [--limit N]
ticktick calendar event show EVENT_ID
ticktick calendar event task EVENT_ID
ticktick --fields title,sourceType,linkedTaskId,calendarName calendar event list [--limit N]
```

### Filters (Smart Lists)

```bash
ticktick filter list
ticktick filter show FILTER_ID
ticktick filter create "NAME" [--priority high|medium|low|none]... [--date today|tomorrow|thisweek|nextweek|thismonth|nextmonth|overdue|nodate|repeat] [--tag TAG]...
ticktick filter edit FILTER_ID [--name "NEW"] [--priority P]... [--date D] [--tag T]...
ticktick filter delete FILTER_ID --yes
```

### Templates

```bash
ticktick template list
ticktick template show TEMPLATE_ID
ticktick template create "TITLE" [--content "TEXT"] [--items "A,B,C"] [--tag TAG]...
ticktick template delete TEMPLATE_ID --yes
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
ticktick [--human] [--quiet] [--output json|csv|yaml] [--fields FIELDS] [--dry-run] [--verbose] [--profile NAME] [--offset N] [--all] COMMAND
```

| Flag | Description |
|------|-------------|
| `--human` | Rich table output instead of JSON |
| `--quiet`, `-q` | Bare output — only IDs, one per line. Messages are suppressed. Errors still go to stderr. Takes precedence over `--human` and `--output`. |
| `--output FORMAT` | `json` (default), `csv`, `yaml` |
| `--fields FIELDS` | Comma-separated field list: `--fields id,title,priority` |
| `--dry-run` | Preview actions without making API calls |
| `--verbose` | Debug output |
| `--profile NAME` | Auth profile (default: `default`) |
| `--offset N` | Skip first N items in list output (client-side pagination) |
| `--all` | Return all items, ignoring `--limit`. No pagination metadata in output. |

### Pagination

List commands support client-side pagination. JSON output includes pagination metadata:

```json
{"ok": true, "data": [...], "count": 10, "total": 42, "offset": 0, "has_more": true}
```

- `--offset N` skips the first N items before returning results
- Command-level `--limit` caps how many items are returned after the offset
- `--all` returns everything with no pagination metadata (just `count`)

### Environment Variables

Global options can be set via environment variables as defaults:

| Variable | Overrides | Example |
|----------|-----------|---------|
| `TICKTICK_OUTPUT` | `--output` | `export TICKTICK_OUTPUT=yaml` |
| `TICKTICK_PROFILE` | `--profile` | `export TICKTICK_PROFILE=work` |
| `TICKTICK_FIELDS` | `--fields` | `export TICKTICK_FIELDS=id,title,priority` |
| `TICKTICK_QUIET` | `--quiet` | `export TICKTICK_QUIET=1` |

Command-line flags always take precedence over environment variables.

### Quiet mode examples

```bash
ticktick task list -q              # Just task IDs, one per line
ticktick task list -q | wc -l      # Count tasks
ticktick task list -q | xargs -I{} ticktick task done {}  # Complete all tasks
ticktick task add "Buy milk" -q    # Just the new task ID
```

## TTY Auto-Detection

The CLI automatically detects whether stdout is a terminal (TTY) and adjusts output format:

- **Terminal (TTY):** Rich table output is used automatically (equivalent to `--human`).
- **Piped / non-TTY:** JSON output is used (agent-friendly default).

Explicit flags always take precedence over auto-detection:

| Scenario | Result |
|----------|--------|
| `ticktick task list` (in terminal) | Rich table |
| `ticktick task list \| jq .` | JSON |
| `ticktick --human task list` | Rich table (explicit) |
| `ticktick --output json task list` (in terminal) | JSON (explicit) |
| `ticktick --output csv task list` | CSV (explicit) |

This means agents piping output always get structured JSON, while interactive users see human-readable tables without needing `--human`.

## Idempotent Creates (`--if-not-exists`)

All create/add commands support `--if-not-exists` for safe retries. When set, the CLI checks if a resource with the same name/title already exists before creating. If found, it returns the existing resource with exit code 0 instead of creating a duplicate.

Supported commands:
- `ticktick task add "TITLE" --if-not-exists` — matches by title (and project if `--project` given)
- `ticktick project create "NAME" --if-not-exists` — matches by project name
- `ticktick tag create "NAME" --if-not-exists` — matches by tag name/label
- `ticktick filter create "NAME" --if-not-exists` — matches by filter name
- `ticktick template create "TITLE" --if-not-exists` — matches by template title
- `ticktick habit create "NAME" --if-not-exists` — matches by habit name

JSON response when resource already exists:

```json
{"ok": true, "data": {...}, "already_exists": true}
```

This enables idempotent operations — agents can safely retry create commands without duplicating resources.

## Output Contract

All commands return:

```
Success (list):  {"ok": true, "data": [...], "count": N, "total": T, "offset": O, "has_more": bool}
Success (--all): {"ok": true, "data": [...], "count": N}
Success (item):  {"ok": true, "data": {...}}
Existing:        {"ok": true, "data": {...}, "already_exists": true}
Message:         {"ok": true, "message": "Task created."}
Error:           {"ok": false, "error": "description"}
```

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Usage / input error |
| `3` | Authentication failure |
| `4` | Resource not found |
| `5` | Rate limited (transient, safe to retry) |
| `6` | Conflict / resource already exists |

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

- Any read command (`list`, `show`, `search`, `today`, `overdue`, `status`, `sync`, `stats`, `heatmap`, `activity`)
- `ticktick config list` / `ticktick config path`
- `ticktick schema`
- `ticktick focus status`

### Ask user first

- Creating tasks, projects, tags, habits, filters, templates (`add`, `create`)
- Editing or moving tasks (`edit`, `move`, `convert`)
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
- 314 tests, CI via GitHub Actions

## Build & Test

```bash
pip install -e ".[dev]"
pytest -v               # 314 tests
```
