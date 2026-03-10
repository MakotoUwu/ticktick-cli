<p align="center">
  <h1 align="center">ticktick-cli</h1>
  <p align="center">
    <strong>Agent-native command-line interface for <a href="https://ticktick.com/">TickTick</a></strong>
    <br />
    Full API coverage &middot; JSON-first &middot; Built for AI agents and humans alike
  </p>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/TickTick_API-100%25_coverage-brightgreen" alt="API Coverage">
  <img src="https://img.shields.io/badge/tests-115_passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/output-JSON_%7C_Rich_Tables-blue" alt="Output Modes">
</p>

---

I was frustrated that no proper TickTick CLI existed. The official API covers only tasks and projects, third-party SDKs are incomplete, MCP servers add unnecessary context overhead, and none of these approaches are designed for the way modern AI agents actually work. So I built `ticktick-cli` -- a CLI that covers **100% of TickTick's API surface** (including the unofficial V2 endpoints), outputs **structured JSON by default**, and works equally well when invoked by a human or by Claude Code via Bash.

### Why CLI, not MCP or SDK?

The [emerging consensus](https://steipete.me/posts/2025/peekaboo-2-freeing-the-cli-from-its-mcp-shackles) from practitioners like [Peter Steinberger](https://github.com/steipete) and [Armin Ronacher](https://lucumr.pocoo.org/2025/7/3/tools/) is clear: **CLI-first, MCP only when necessary.** AI coding agents (Claude Code, Codex, Cursor) already invoke tools via shell -- that's their native interface. Adding an MCP server is an extra process, an extra protocol, and [extra context pollution](https://lucumr.pocoo.org/2025/12/13/skills-vs-mcp/) that doesn't add value when a CLI already outputs structured JSON. Benchmarks show CLI achieves higher task completion at equivalent token cost. The Unix philosophy was accidentally designed for AI agents decades before they existed.

---

## Highlights

- **JSON output by default** -- structured `{"ok": true, "data": [...]}` responses, parseable by any agent or script
- **`--human` flag** -- switch to rich terminal tables with a single flag
- **100% API coverage** -- tasks, subtasks, projects, folders, tags, kanban columns, habits, focus/pomodoro stats, user profile
- **Dual API support** -- V1 (official OAuth 2.0) + V2 (unofficial session-based) for full feature access
- **Agent-friendly design** -- no interactive prompts, `--yes` flags, deterministic exit codes (0/1/2)
- **Multiple profiles** -- `--profile work` / `--profile personal` for separate accounts
- **Security-first** -- OAuth CSRF protection, encrypted credential storage (600 permissions), env var support for secrets

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [Output Format](#output-format)
- [Agent Integration](#agent-integration)
- [Authentication](#authentication)
- [Configuration](#configuration)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

## Installation

### From source (recommended for now)

```bash
git clone https://github.com/mamorka/ticktick-cli.git
cd ticktick-cli
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### pip (once published)

```bash
pip install ticktick-cli
```

### pipx (isolated install)

```bash
pipx install ticktick-cli
```

## Quick Start

### 1. Authenticate

```bash
# V2 session (recommended -- unlocks all features)
ticktick auth login-v2 --username you@email.com
# Password is prompted securely (or set TICKTICK_PASSWORD env var)

# V1 OAuth (official API -- tasks & projects only)
export TICKTICK_CLIENT_ID="your_client_id"
export TICKTICK_CLIENT_SECRET="your_client_secret"
ticktick auth login --client-id "$TICKTICK_CLIENT_ID" --client-secret "$TICKTICK_CLIENT_SECRET"
```

### 2. Start using it

```bash
# List your tasks (JSON)
ticktick task list

# Same thing, but as a rich table
ticktick --human task list

# Add a task
ticktick task add "Review pull request" --priority high --due tomorrow

# Complete it
ticktick task done TASK_ID

# What's overdue?
ticktick task overdue

# Check your habits
ticktick --human habit list

# Focus stats for the last 30 days
ticktick focus heatmap --days 30

# Full account sync
ticktick sync
```

### JSON output (default)

```json
{
  "ok": true,
  "data": [
    {
      "id": "abc123",
      "title": "Review pull request",
      "priority": "high",
      "status": "active",
      "dueDate": "2026-03-11T00:00:00.000+0000"
    }
  ],
  "count": 1
}
```

### Rich table output (`--human`)

```
                             Tasks
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ id       ┃ title                  ┃ priority ┃ dueDate      ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ abc123   │ Review pull request    │ high     │ 2026-03-11   │
│ def456   │ Buy groceries          │ none     │ 2026-03-12   │
└──────────┴────────────────────────┴──────────┴──────────────┘
```

## Commands

| Domain | Commands | API |
|--------|----------|-----|
| **Tasks** | `add` `list` `show` `edit` `done` `abandon` `delete` `move` `search` `today` `overdue` `completed` `trash` `pin` `unpin` `batch-add` | V1+V2 |
| **Subtasks** | `set` `unset` `list` | V2 |
| **Projects** | `list` `create` `show` `edit` `delete` | V1+V2 |
| **Folders** | `list` `create` `rename` `delete` | V2 |
| **Tags** | `list` `create` `edit` `rename` `merge` `delete` | V2 |
| **Kanban** | `column list` `create` `edit` `delete` | V2 |
| **Habits** | `list` `show` `create` `edit` `delete` `checkin` `history` `archive` `unarchive` | V2 |
| **Focus** | `heatmap` `by-tag` | V2 |
| **User** | `profile` `status` `stats` `preferences` | V2 |
| **Config** | `set` `get` `list` `path` | -- |
| **Auth** | `login` `login-v2` `logout` `status` | -- |
| **Sync** | Full state dump (all tasks, projects, tags, groups) | V2 |

### Global Options

| Flag | Description |
|------|-------------|
| `--human` | Rich table output instead of JSON |
| `--verbose` | Enable debug output |
| `--profile NAME` | Auth profile to use (default: `default`) |
| `--version` | Show version |
| `--help` | Show help for any command |

## Output Format

Every command returns a consistent JSON envelope:

```
Success:  {"ok": true, "data": <result>, "count": <n>}
Message:  {"ok": true, "message": "Task created."}
Error:    {"ok": false, "error": "description"}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (API error, invalid input) |
| `2` | Authentication error (not logged in, expired token) |

## Agent Integration

`ticktick-cli` follows the [agent-native CLI](https://www.infoq.com/articles/ai-agent-cli/) design pattern -- the same approach used by `gh`, `git`, and `docker` with Claude Code, Codex, and Cursor. An [`AGENTS.md`](AGENTS.md) file is included for agent discovery (compatible with the [AGENTS.md standard](https://agents.md/) adopted by 60,000+ repositories).

**No ANSI escape codes in JSON mode** -- output is always clean, parseable JSON.

**No interactive prompts** -- use `--yes` to skip confirmations for destructive actions:
```bash
ticktick task delete TASK_ID --yes
ticktick project delete PROJECT_ID --yes
```

**Deterministic exit codes** -- agents can check `$?` to determine success/failure without parsing output.

**Pipe-friendly** -- combine with `jq` for complex queries:
```bash
# Get titles of all high-priority tasks
ticktick task list --priority high | jq -r '.data[].title'

# Count overdue tasks
ticktick task overdue | jq '.count'

# Get habit names and streaks
ticktick habit list | jq '.data[] | {name, currentStreak}'
```

**Environment variables for auth** -- no secrets in command args:
```bash
export TICKTICK_USERNAME="you@email.com"
export TICKTICK_PASSWORD="secret"
export TICKTICK_CLIENT_ID="your_id"
export TICKTICK_CLIENT_SECRET="your_secret"
```

> **Why not MCP?** MCP servers add a separate process, a custom protocol, and [consume thousands of tokens](https://lucumr.pocoo.org/2025/12/13/skills-vs-mcp/) just from tool descriptions being loaded. A CLI that outputs JSON is already a perfect tool interface -- Claude Code calls it via Bash, parses the JSON, and moves on. Zero overhead, universal compatibility, and it works with *any* agent that has shell access.

## Authentication

### V1: Official OAuth 2.0

The official API supports tasks and projects. Requires a developer app:

1. Go to [developer.ticktick.com](https://developer.ticktick.com/) and create an app
2. Set redirect URI to `http://localhost:8080/callback`
3. Run:
```bash
ticktick auth login --client-id YOUR_ID --client-secret YOUR_SECRET
```
This opens your browser for OAuth authorization and stores the token locally.

### V2: Session-based (recommended)

The unofficial V2 API unlocks everything: habits, tags, focus stats, kanban, folders, subtasks, and more.

```bash
ticktick auth login-v2 --username you@email.com
# Password is prompted securely
```

> **Note:** V2 uses the same API the TickTick web app uses. It sends your password over HTTPS to TickTick's servers. If you're uncomfortable with this, use V1 OAuth for the subset of features it supports.

### Multiple profiles

```bash
ticktick --profile work auth login-v2 --username work@company.com
ticktick --profile personal auth login-v2 --username me@gmail.com

ticktick --profile work task list
ticktick --profile personal habit list
```

### Check auth status

```bash
ticktick auth status
```

## Configuration

Config files live at `~/.config/ticktick-cli/<profile>/` (XDG-compliant).

```bash
# See where config is stored
ticktick config path

# List all settings
ticktick config list

# Set a value
ticktick config set default_project "Work"

# Get a value
ticktick config get default_project
```

## Security

- **Credentials stored with `600` permissions** -- only your user can read `auth.json`
- **Atomic file writes** -- no TOCTOU race condition where credentials are briefly world-readable
- **OAuth CSRF protection** -- `state` parameter validated on callback
- **No secrets in process args** -- password is prompted interactively or read from env vars
- **Error messages sanitized** -- API responses truncated to prevent token/credential leakage
- **Profile name validation** -- prevents directory traversal attacks

## Contributing

```bash
# Clone and set up
git clone https://github.com/mamorka/ticktick-cli.git
cd ticktick-cli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -v

# All 115 tests should pass
```

### Project Structure

```
src/ticktick_cli/
  api/
    base.py        # Shared HTTP transport
    v1.py          # Official OAuth2 API client
    v2.py          # Unofficial session API client
    client.py      # Unified TickTickClient
  commands/
    auth_cmd.py    # login, login-v2, logout, status
    task_cmd.py    # 16 task commands
    project_cmd.py # CRUD for projects
    folder_cmd.py  # CRUD for folders
    tag_cmd.py     # tag management
    kanban_cmd.py  # kanban columns
    subtask_cmd.py # subtask parent/child
    habit_cmd.py   # habit tracking
    focus_cmd.py   # pomodoro/focus stats
    user_cmd.py    # profile, stats, preferences
    config_cmd.py  # CLI config management
  auth.py          # OAuth2 + V2 auth flows
  config.py        # XDG config management
  output.py        # JSON/Rich table output
  exceptions.py    # Custom exception hierarchy
  cli.py           # Main entry point
```

## Roadmap

- [ ] Publish to PyPI
- [ ] Shell completions (bash, zsh, fish)
- [ ] Token auto-refresh for V1 OAuth
- [ ] Homebrew formula
- [ ] CI/CD with GitHub Actions

## License

[MIT](LICENSE)
