---
description: Capture a TickTick task from natural language using the CLI
---

# TickTick Capture

Capture the user's request as a TickTick task using `ticktick`.

Use `$ARGUMENTS` as the raw task request.

Workflow:

1. Run `ticktick auth status` first. If not authenticated, stop and tell the user to authenticate themselves.
2. Preview the create operation with a dry run:
   - `ticktick --dry-run --output json task add "$ARGUMENTS"`
3. If the task details need clarification, ask one concise question.
4. Before the real create, confirm with the user because this mutates their TickTick account.
5. After confirmation, run the real `ticktick task add ...` command with the best inferred fields.
6. Return the created task ID and title.
