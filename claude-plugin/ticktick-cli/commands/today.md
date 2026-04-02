---
description: Review today's TickTick agenda with tasks, focus status, and upcoming calendar items
---

# TickTick Today

Use the installed `ticktick` CLI to summarize today's working context.

Steps:

1. Run `ticktick auth status` first. If the user is not authenticated, stop and tell them to log in themselves.
2. Run read-only commands only:
   - `ticktick --output json task today`
   - `ticktick --output json task overdue`
   - `ticktick --output json focus status`
   - `ticktick --output json calendar event list --limit 10`
3. Summarize:
   - today's tasks
   - overdue tasks
   - current focus timer state
   - upcoming calendar events
4. Keep the output concise and action-oriented.
