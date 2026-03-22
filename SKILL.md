---
name: ticktick-cli
description: "Agent-native CLI for TickTick task management: 70+ commands covering tasks, projects, habits, focus/pomodoro, kanban, tags, filters, templates, subtasks, and comments with JSON-first output."
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - ticktick
        - python3
    emoji: "\u2705"
    homepage: https://github.com/mamorka/ticktick-cli
    install:
      - kind: uv
        package: ticktick-cli
        bins:
          - ticktick
---

# ticktick-cli

Agent-native command-line interface for [TickTick](https://ticktick.com/) with 100% API coverage.
JSON output by default, no interactive prompts, deterministic exit codes. Works equally well
when called by a human or by an AI agent via shell.

## Prerequisites

- Python 3.10+
- A TickTick account (free or premium)
- V2 session auth (recommended) or V1 OAuth credentials

## Installation

```bash
# From source (recommended for now)
git clone https://github.com/mamorka/ticktick-cli.git
cd ticktick-cli
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Or via pip once published
pip install ticktick-cli
```

## Authentication

Before using any commands, authenticate:

```bash
# V2 session (recommended -- unlocks all features including habits, focus, kanban, tags)
ticktick auth login-v2 --username you@email.com

# V1 OAuth (official API -- tasks and projects only)
ticktick auth login --client-id YOUR_ID --client-secret YOUR_SECRET

# Check auth status
ticktick auth status
```

Authentication credentials can also be set via environment variables:

```bash
export TICKTICK_USERNAME="you@email.com"
export TICKTICK_PASSWORD="secret"
export TICKTICK_CLIENT_ID="your_id"
export TICKTICK_CLIENT_SECRET="your_secret"
```

## Discovery

```bash
ticktick schema          # Full CLI structure (commands, flags, types) for agent introspection
ticktick --help          # Top-level help
ticktick <command> --help  # Command-specific help
```

## Key Capabilities

- **70+ commands** across 15 domains (tasks, projects, folders, tags, habits, focus/pomodoro, kanban, filters, templates, subtasks, comments, user, config, auth, sync)
- **Dual API support**: V1 (official OAuth 2.0) + V2 (unofficial session-based) for full feature access
- **JSON-first output**: structured `{"ok": true, "data": [...], "count": N}` responses
- **Multiple output formats**: JSON (default), CSV, YAML, or rich terminal tables (`--human`)
- **Dry-run mode**: preview any mutating command without making API calls (`--dry-run`)
- **Field selection**: return only what you need with `--fields id,title,priority`
- **Schema introspection**: `ticktick schema` dumps the full CLI structure for agent discovery
- **Natural language dates**: `--due tomorrow`, `--due "next monday"`, `--due "in 3 days"`
- **No interactive prompts**: all confirmations via `--yes` flag
- **Deterministic exit codes**: 0 success, 1 error, 2 auth error

## Usage Examples

### Tasks

```bash
# List tasks as JSON
ticktick task list

# List tasks as a rich table
ticktick --human task list

# Add a task with natural language due date
ticktick task add "Review pull request" --priority high --due tomorrow --tag work

# View today's tasks
ticktick task today

# Find overdue tasks
ticktick task overdue

# Search tasks
ticktick task search "quarterly report"

# Complete one or more tasks
ticktick task done TASK_ID

# Edit a task
ticktick task edit TASK_ID --title "Updated title" --priority medium

# Move task to another project
ticktick task move TASK_ID --to PROJECT_ID

# Dry-run a delete (preview without executing)
ticktick --dry-run task delete TASK_ID --yes

# View completed tasks from the last week
ticktick task completed --from "7 days ago"

# Batch add tasks from a JSON file
ticktick task batch-add --file tasks.json

# Select only specific fields
ticktick task list --fields id,title,priority,dueDate
```

### Projects

```bash
ticktick project list
ticktick project create "Work Tasks" --color "#FF6B6B"
ticktick project show PROJECT_ID
ticktick project delete PROJECT_ID --yes
```

### Habits

```bash
ticktick habit list
ticktick habit create "Meditate" --type boolean
ticktick habit checkin HABIT_ID
ticktick habit history HABIT_ID --days 30
```

### Focus / Pomodoro

```bash
ticktick focus start --duration 25 --note "deep work"
ticktick focus status
ticktick focus stop --save
ticktick focus stats
ticktick focus heatmap --days 30
```

### Tags

```bash
ticktick tag list
ticktick tag create "urgent" --color "#FF0000"
ticktick tag rename "old-name" "new-name"
ticktick tag merge "source-tag" "target-tag"
```

### Kanban Columns

```bash
ticktick column list PROJECT_ID
ticktick column create PROJECT_ID "In Progress"
```

### Filters (Smart Lists)

```bash
ticktick filter list
ticktick filter create "High Priority This Week" --priority high --date thisweek
```

### Templates

```bash
ticktick template list
ticktick template create "Weekly Review" --content "Review goals" --items "Check tasks,Review habits,Plan next week"
```

### Subtasks

```bash
ticktick subtask list PARENT_TASK_ID
ticktick subtask set TASK_ID --parent PARENT_ID
```

### Comments and Activity

```bash
ticktick task comment list TASK_ID
ticktick task comment add TASK_ID "Waiting on design review"
ticktick task activity TASK_ID
```

### User and Sync

```bash
ticktick user profile
ticktick user stats
ticktick sync
```

### Pipe-Friendly

```bash
# Get titles of high-priority tasks
ticktick task list --priority high | jq -r '.data[].title'

# Count overdue tasks
ticktick task overdue | jq '.count'

# Export tasks as CSV
ticktick task list --output csv > tasks.csv
```

## Output Contract

All commands return a consistent JSON envelope:

```
Success:  {"ok": true, "data": [...], "count": N}
Message:  {"ok": true, "message": "Task created."}
Error:    {"ok": false, "error": "description"}
```

Exit codes: `0` success, `1` error, `2` auth error.

## Global Flags

| Flag | Description |
|------|-------------|
| `--human` | Rich table output instead of JSON |
| `--output FORMAT` | `json` (default), `csv`, `yaml` |
| `--fields FIELDS` | Comma-separated field list |
| `--dry-run` | Preview actions without making API calls |
| `--verbose` | Debug output |
| `--profile NAME` | Auth profile (default: `default`) |

## Safety Guidelines

**Always safe to run:** `list`, `show`, `search`, `today`, `overdue`, `status`, `sync`, `stats`, `schema`, `heatmap`, `activity`

**Ask user before:** creating, editing, moving, or completing tasks; starting/stopping focus; checking in habits

**Require explicit confirmation:** any `delete` operation (always use `--yes`), auth commands, batch operations
