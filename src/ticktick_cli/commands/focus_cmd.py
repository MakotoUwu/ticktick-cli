"""Focus / Pomodoro statistics commands — heatmap, by-tag (V2 only)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_error, output_item, output_list


def _resolve_date_range(
    from_date: str | None, to_date: str | None, days: int
) -> tuple[date, date]:
    """Resolve CLI options to a (start, end) date pair."""
    if from_date and to_date:
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
    else:
        end = date.today()
        start = end - timedelta(days=days)
    return start, end


@click.group("focus")
def focus_group() -> None:
    """Focus / Pomodoro statistics (V2)."""


@focus_group.command("heatmap")
@click.option("--from", "from_date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--days", type=int, default=30, help="Number of days (default: 30)")
@click.pass_context
def focus_heatmap(ctx: click.Context, from_date: str | None, to_date: str | None, days: int) -> None:
    """View focus time heatmap data."""
    client = get_client(ctx.obj.get("profile", "default"))
    start, end = _resolve_date_range(from_date, to_date, days)

    try:
        data = client.v2.get_focus_heatmap(start, end)
        if isinstance(data, list) and data and "day" in data[0]:
            # V2 returns [{duration, day, timezone}, ...]
            rows = [
                {"date": item["day"], "minutes": item.get("duration", 0)}
                for item in data
                if item.get("duration", 0) > 0  # only show days with focus time
            ]
            if not rows:
                rows = [{"date": item["day"], "minutes": 0} for item in data[-7:]]
            output_list(rows, columns=["date", "minutes"], title="Focus Heatmap", ctx=ctx)
        elif isinstance(data, list):
            output_list(data, title="Focus Heatmap", ctx=ctx)
        elif isinstance(data, dict):
            output_item(data, ctx)
        else:
            output_item({"raw": data}, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@focus_group.command("by-tag")
@click.option("--from", "from_date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--days", type=int, default=30, help="Number of days (default: 30)")
@click.pass_context
def focus_by_tag(ctx: click.Context, from_date: str | None, to_date: str | None, days: int) -> None:
    """View focus time distribution by tag."""
    client = get_client(ctx.obj.get("profile", "default"))
    start, end = _resolve_date_range(from_date, to_date, days)

    try:
        data = client.v2.get_focus_by_tag(start, end)
        if isinstance(data, dict) and any(
            k in data for k in ("tagDurations", "projectDurations", "taskDurations")
        ):
            # V2 returns {tagDurations: {name: mins}, projectDurations: ..., taskDurations: ...}
            sections = []
            for section_key, label in [
                ("projectDurations", "project"),
                ("tagDurations", "tag"),
                ("taskDurations", "task"),
            ]:
                for name, minutes in sorted(
                    data.get(section_key, {}).items(), key=lambda x: -x[1]
                ):
                    sections.append({"type": label, "name": name, "minutes": minutes})
            output_list(
                sections,
                columns=["type", "name", "minutes"],
                title="Focus Distribution",
                ctx=ctx,
            )
        elif isinstance(data, list):
            output_list(data, title="Focus Distribution", ctx=ctx)
        else:
            output_item(data, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
