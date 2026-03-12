"""Test natural language date parsing."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from ticktick_cli.dates import parse_date

_FMT = "%Y-%m-%dT%H:%M:%S.000+0000"
_FIXED_NOW = datetime(2026, 3, 11, 14, 30, 0)


def _fixed_parse(date_str: str) -> str:
    """Call parse_date with a fixed 'now' so tests are deterministic."""
    with patch("ticktick_cli.dates.datetime") as mock_dt:
        mock_dt.now.return_value = _FIXED_NOW
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        return parse_date(date_str)


class TestBasicDates:
    def test_today(self) -> None:
        result = _fixed_parse("today")
        assert result == "2026-03-11T00:00:00.000+0000"

    def test_tomorrow(self) -> None:
        result = _fixed_parse("tomorrow")
        assert result == "2026-03-12T00:00:00.000+0000"

    def test_yesterday(self) -> None:
        result = _fixed_parse("yesterday")
        assert result == "2026-03-10T00:00:00.000+0000"

    def test_case_insensitive(self) -> None:
        result = _fixed_parse("TODAY")
        assert result == "2026-03-11T00:00:00.000+0000"

    def test_whitespace_trimmed(self) -> None:
        result = _fixed_parse("  tomorrow  ")
        assert result == "2026-03-12T00:00:00.000+0000"


class TestRelativeOffsets:
    def test_plus_3d(self) -> None:
        result = _fixed_parse("+3d")
        assert result == "2026-03-14T00:00:00.000+0000"

    def test_plus_1w(self) -> None:
        result = _fixed_parse("+1w")
        assert result == "2026-03-18T00:00:00.000+0000"

    def test_plus_2m(self) -> None:
        result = _fixed_parse("+2m")
        assert result == "2026-05-11T00:00:00.000+0000"

    def test_minus_2d(self) -> None:
        result = _fixed_parse("-2d")
        assert result == "2026-03-09T00:00:00.000+0000"

    def test_plus_0d(self) -> None:
        result = _fixed_parse("+0d")
        assert result == "2026-03-11T00:00:00.000+0000"


class TestWeekdays:
    def test_next_friday(self) -> None:
        # 2026-03-11 is Wednesday, next Friday = 2026-03-13
        result = _fixed_parse("friday")
        assert result == "2026-03-13T00:00:00.000+0000"

    def test_next_monday(self) -> None:
        # 2026-03-11 is Wednesday, next Monday = 2026-03-16
        result = _fixed_parse("monday")
        assert result == "2026-03-16T00:00:00.000+0000"

    def test_explicit_next_friday(self) -> None:
        result = _fixed_parse("next friday")
        assert result == "2026-03-13T00:00:00.000+0000"

    def test_this_friday(self) -> None:
        result = _fixed_parse("this friday")
        assert result == "2026-03-13T00:00:00.000+0000"

    def test_abbreviated_weekday(self) -> None:
        result = _fixed_parse("fri")
        assert result == "2026-03-13T00:00:00.000+0000"

    def test_sunday(self) -> None:
        # 2026-03-11 is Wednesday, next Sunday = 2026-03-15
        result = _fixed_parse("sun")
        assert result == "2026-03-15T00:00:00.000+0000"

    def test_same_day_goes_to_next_week(self) -> None:
        # 2026-03-11 is Wednesday, asking for "wednesday" should give next week
        result = _fixed_parse("wednesday")
        assert result == "2026-03-18T00:00:00.000+0000"


class TestEndOf:
    def test_end_of_week(self) -> None:
        result = _fixed_parse("eow")
        # Next Sunday from 2026-03-11 (Wednesday) = 2026-03-15
        assert result == "2026-03-15T00:00:00.000+0000"

    def test_end_of_month(self) -> None:
        result = _fixed_parse("eom")
        assert result == "2026-03-31T00:00:00.000+0000"


class TestISOFallback:
    def test_iso_date(self) -> None:
        result = parse_date("2026-06-15")
        assert result == "2026-06-15T00:00:00.000+0000"

    def test_iso_datetime(self) -> None:
        result = parse_date("2026-06-15T10:30:00")
        assert result == "2026-06-15T10:30:00.000+0000"


class TestErrors:
    def test_unparseable_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse date"):
            parse_date("not a date at all")

    def test_error_shows_suggestions(self) -> None:
        with pytest.raises(ValueError, match=r"today.*tomorrow.*monday"):
            parse_date("gibberish")
