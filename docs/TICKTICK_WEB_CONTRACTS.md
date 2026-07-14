# TickTick Web Contracts

This file records the smallest stable web-app behavior that the CLI needs when
TickTick's official Open API does not expose a product feature. It is an
implementation contract, not a copy of browser credentials or captured private
task data.

## Focus Estimates

TickTick's current product supports Estimated Pomo and Estimated Duration on a
task. The official behavior is described in TickTick's
[Estimation](https://help.ticktick.com/articles/7055792921664028672) and
[Start Focus](https://help.ticktick.com/articles/7055782010496745472) guides.

Browser inspection on 2026-07-12 confirmed that task records returned by the
web app's incremental batch response carry user-scoped `focusSummaries` rows:

```json
{
  "focusSummaries": [
    {
      "userId": 123,
      "estimatedPomo": 2,
      "estimatedDuration": 5400,
      "pomoCount": 0,
      "pomoDuration": 0,
      "stopwatchDuration": 0
    }
  ]
}
```

- `estimatedPomo` is a Pomodoro count.
- `estimatedDuration` is stored in seconds.
- Estimates are user-scoped. The CLI flattens estimate fields only when exactly
  one non-empty summary exists; multiple summaries are reported as ambiguous.
- The official V1 folder snapshot does not currently provide these fields. The
  CLI reads the V2 task detail once when recommending or starting estimated
  focus.

## Duration Policy

`ticktick focus recommend TASK_ID` is read-only. `ticktick focus start --task
TASK_ID --auto-duration` applies the same resolver and then starts the session:

- Estimated Duration up to 15 minutes: use the estimate, with a 5-minute floor.
- Estimated Duration from 16 through 35 minutes: start one 25-minute block.
- Estimated Duration over 35 minutes: start one 50-minute block.
- Estimated Pomo without duration: start the first 25-minute Pomodoro.
- Missing or ambiguous estimate: use the requested fallback, 25 minutes by
  default.
- Rate-limited estimate read: start the fallback and return
  `durationSource: default_rate_limited` instead of retrying repeatedly.

The command output always reports `focusMinutes`, `durationSource`,
`estimatedDurationMinutes`, and `estimatedPomo`, so callers can distinguish
native estimates from fallbacks.

## Timed Task Scheduling

The official `POST /open/v1/task/filter` endpoint accepts multiple project IDs
and returns task timing fields including `startDate`, `dueDate`, `isAllDay`, and
`timeZone`. `ticktick focus due --folder-id FOLDER_ID` uses that official path
to identify the positive-length timed task whose window is active now.

- All-day, completed, untimed, and zero-length tasks are ignored.
- The task's start/end interval is the planned focus length.
- A late check uses only the remaining interval.
- Fewer than five remaining minutes is too late to start automatically.
- A single timer is capped at 180 minutes.
- When timed tasks overlap, the most recently started task wins.

This selection command is read-only. The Mission Control runtime owns the
separate opt-in decision to start the returned task.

## Low-Request Task Batch Edits

Browser inspection on 2026-07-14 confirmed the task synchronization and write
contracts used by the current TickTick web app:

- `GET /api/v3/batch/check/0` returns the current account task state in one
  response.
- `POST /api/v2/batch/task` accepts `add`, `update`, and `delete` arrays and
  returns per-item `id2etag` receipts plus `id2error` failures.

`ticktick task batch-edit --file updates.json` uses the existing authenticated
V2 client and that batch-write contract. It performs no lookup when every row
contains `projectId`. If one or more rows omit `projectId`, it performs exactly
one account-state read and resolves all missing project IDs before issuing one
write. A non-empty `id2error` response fails the command even when the HTTP
request itself returned 200.

The input accepts canonical web fields and a small set of agent-friendly
aliases. Use explicit UTC offsets for exact local times:

```json
[
  {
    "id": "TASK_ID",
    "projectId": "PROJECT_ID",
    "title": "Updated title",
    "priority": "high",
    "start": "2026-07-15T08:45:00+02:00",
    "due": "2026-07-15T09:15:00+02:00",
    "allDay": false,
    "timezone": "Europe/Brussels"
  }
]
```

The command is deliberately limited to 100 task edits. Parent/subtask changes
remain on the dedicated `/batch/taskParent` command path because adding a
`parentId` to ordinary task updates did not persist reliably during inspection.

## Maintenance Rule

Use Chrome DevTools only to discover or verify a missing contract. Once the
behavior is understood, add a typed CLI field or command, focused tests, and a
short contract update here. Normal Mission Control operation should then use
the CLI, not browser automation. Never commit cookies, tokens, authorization
headers, full private responses, or temporary captures.
