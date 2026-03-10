# AGENTS.md — Agent Guide for ticktick-cli

This file describes how AI agents should use `ticktick-cli` to manage TickTick tasks, habits, and more.

## Overview

`ticktick-cli` is an agent-native CLI for TickTick. All commands return structured JSON by default. No interactive prompts — use `--yes` to skip confirmations.

## Authentication

Before using any commands, ensure the user has authenticated:

```bash
ticktick auth status
```

If not authenticated, **ask the user** to run auth commands themselves (never handle passwords).

## Output Contract

```
Success:  {"ok": true, "data": <result>, "count": <n>}
Message:  {"ok": true, "message": "..."}
Error:    {"ok": false, "error": "..."}
```

Exit codes: `0` = success, `1` = error, `2` = auth error.

## Core Commands

### Tasks

```bash
# List tasks (most recent first)
ticktick task list [--limit N] [--priority high|medium|low|none] [--project PROJECT_ID] [--tag TAG]

# Today's tasks
ticktick task today

# Overdue tasks
ticktick task overdue

# Search by keyword
ticktick task search "QUERY"

# Show single task details
ticktick task show TASK_ID

# Create a task
ticktick task add "TITLE" [--priority high|medium|low] [--project PROJECT_ID] [--due DATE] [--tag TAG]

# Complete a task
ticktick task done TASK_ID

# Delete (requires --yes for non-interactive)
ticktick task delete TASK_ID --yes

# Move task to another project
ticktick task move TASK_ID --to PROJECT_ID

# Completed tasks history
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

### User

```bash
ticktick user profile
ticktick user stats
ticktick user status
```

### Other

```bash
ticktick folder list
ticktick column list PROJECT_ID
ticktick sync                          # Full account state dump
ticktick config list                   # Current config
```

## Common Agent Workflows

### Daily briefing
```bash
ticktick task today
ticktick task overdue
ticktick habit list
```

### Create and manage tasks
```bash
ticktick task add "Review PR #42" --priority high --due tomorrow
# ... later ...
ticktick task done TASK_ID
```

### Parse JSON with jq
```bash
ticktick task list --priority high | jq -r '.data[].title'
ticktick task overdue | jq '.count'
```

## Important Notes

- All destructive operations (delete, abandon) require `--yes` flag
- `--human` flag is a **global option** — goes BEFORE the command: `ticktick --human task list`
- Task IDs are 24-character hex strings (MongoDB ObjectId format)
- Dates in API responses are ISO 8601 with timezone offset
- V2 commands (habits, focus, tags, folders, columns) require V2 authentication
