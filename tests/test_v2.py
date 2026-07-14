"""Focused tests for the TickTick V2/V3 web transport."""

from unittest.mock import patch

from ticktick_cli.api.v2 import V2Client


def test_sync_web_uses_observed_v3_batch_endpoint() -> None:
    client = V2Client()
    try:
        with patch.object(client, "get", return_value={"checkPoint": 1}) as get:
            assert client.sync_web() == {"checkPoint": 1}
        get.assert_called_once_with("https://api.ticktick.com/api/v3/batch/check/0")
    finally:
        client.close()
