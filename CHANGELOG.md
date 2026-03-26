# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Trusted-publishing-ready GitHub Actions workflow for TestPyPI and PyPI releases
- Release documentation covering local checks, staged TestPyPI publishes, and production PyPI publishes
- **Filters (smart lists)**: `filter list`, `filter show`, `filter create`, `filter edit`, `filter delete` — full CRUD for saved filters with priority, date, and tag conditions
- **Task templates**: `template list`, `template show`, `template create`, `template delete` — save and reuse task templates
- **Task ↔ Note conversion**: `task convert TASK_ID --to note|task` — convert between task and note types
- **Task comments**: `task comment list`, `task comment add`, `task comment delete` — manage task comments
- **Activity history**: `task activity TASK_ID` — view change history for a task
- **Task duplicate**: `task duplicate TASK_ID` — duplicate an existing task
- Pydantic models for Filter, FilterRule, FilterCondition, TaskTemplate, Comment, Activity
- 439 tests (up from 245)

## [0.1.0] - 2026-03-12

### Added

- **Focus/Pomodoro timer control**: `focus start`, `focus stop`, `focus status`, `focus log`, `focus delete`, `focus stats` — full pomodoro lifecycle management from the CLI
- **Natural language dates**: `--due tomorrow`, `--start "next monday"`, `--due "in 3 days"` for task date flags
- **CSV and YAML output**: `--output csv` and `--output yaml` alongside default JSON
- **Field selection**: `--fields id,title,priority` to return only specific columns
- **Dry-run mode**: `--dry-run` flag to preview actions without making API calls
- **Shell completions**: `ticktick completion bash|zsh|fish` for auto-complete
- **Schema command**: `ticktick schema` for agent-discoverable CLI structure
- **Retry with exponential backoff**: automatic retries for transient API errors
- **V1 token auto-refresh**: seamless OAuth token renewal on expiry
- **Pydantic v2 models**: typed models for Task, Project, Tag, Habit, Pomodoro
- **Task commands** (16): add, list, show, edit, done, abandon, delete, move, search, today, overdue, completed, trash, pin, unpin, batch-add
- **Subtask commands** (3): set, unset, list
- **Project commands** (5): list, create, show, edit, delete
- **Folder commands** (4): list, create, rename, delete
- **Tag commands** (6): list, create, edit, rename, merge, delete
- **Kanban column commands** (4): list, create, edit, delete
- **Habit commands** (9): list, show, create, edit, delete, checkin, history, archive, unarchive
- **Focus commands** (8): start, stop, status, log, delete, stats, heatmap, by-tag
- **User commands** (4): profile, status, stats, preferences
- **Config commands** (4): set, get, list, path
- **Auth commands** (5): login (V1 OAuth), login-v2 (session), logout, status, refresh
- **Sync command**: full account state dump
- Dual API support: V1 (OAuth2, official) + V2 (session-based, full feature set)
- JSON-first output with `{"ok": true, "data": [...]}` envelope
- Rich terminal tables via `--human` flag
- Multiple auth profiles via `--profile`
- XDG-compliant config storage with encrypted credentials
- OAuth CSRF protection and secure credential handling
- GitHub Actions CI with Python 3.10–3.13 matrix
- AGENTS.md for AI agent discovery
- 245 tests with comprehensive coverage
