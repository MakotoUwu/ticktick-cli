# ticktick-cli Claude Code plugin

Claude Code plugin for `ticktick-cli`.

This plugin packages a marketplace-ready Claude Code extension around the
published `ticktick-agent-cli` package so Claude can use TickTick through a
stable CLI instead of a custom MCP server.

## What it provides

- A reusable Skill for operating TickTick safely from Claude Code
- Slash commands for agenda review and task capture
- Marketplace metadata for local validation and future directory submission

## Local development

Validate the marketplace and plugin manifests:

```bash
claude plugin validate .
claude plugin validate ./claude-plugin/ticktick-cli
```

Run Claude Code with the plugin loaded directly:

```bash
claude --plugin-dir ./claude-plugin/ticktick-cli
```

## Local marketplace install

From the repository root inside Claude Code:

```text
/plugin marketplace add .
/plugin install ticktick-cli@ticktick-cli-marketplace
```

Restart Claude Code or run `/reload-plugins` after installation.
