"""Tests for TickTick task attachment support."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from ticktick_cli.api.v2 import (
    V2Client,
    _format_attachment_markdown,
    _infer_attachment_file_type,
)
from ticktick_cli.commands.task_cmd import task_group


def _make_ctx(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "human": False,
        "verbose": False,
        "profile": "default",
        "fields": None,
        "dry_run": False,
        "output_format": "json",
        "quiet": False,
        "offset": 0,
        "all": False,
    }
    defaults.update(overrides)
    return defaults


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.v2 = MagicMock()
    client.has_v2 = True
    client.has_v1 = False
    return client


class TestAttachmentHelpers:
    def test_format_attachment_markdown_encodes_filename(self) -> None:
        marker = _format_attachment_markdown("att1", "IMAGE", "my photo (1).jpg")
        assert marker == "![image](att1/my%20photo%20%281%29.jpg)"

    def test_infer_image_type_from_extension(self, tmp_path) -> None:
        path = tmp_path / "photo.jpeg"
        assert _infer_attachment_file_type(path) == "IMAGE"

    def test_infer_pdf_type_from_extension(self, tmp_path) -> None:
        path = tmp_path / "paper.pdf"
        assert _infer_attachment_file_type(path) == "PDF"


class TestV2AttachmentApi:
    def test_batch_tasks_accepts_attachment_sections(self) -> None:
        client = V2Client()

        with patch.object(client, "post", return_value={"id2etag": {}}) as mock_post:
            client.batch_tasks(
                add_attachments=[{"id": "task1", "attachments": [{"id": "att1"}]}],
                update_attachments=[{"id": "task2", "attachments": [{"id": "att2"}]}],
                delete_attachments=[{"id": "task3", "attachments": [{"id": "att3"}]}],
            )

        payload = mock_post.call_args.kwargs["json_data"]
        assert payload["addAttachments"][0]["id"] == "task1"
        assert payload["updateAttachments"][0]["id"] == "task2"
        assert payload["deleteAttachments"][0]["id"] == "task3"

    def test_upload_task_attachment_uses_multipart_v1_endpoint(self, tmp_path) -> None:
        path = tmp_path / "photo.jpg"
        path.write_bytes(b"fake image")
        client = V2Client()
        client.set_session({"t": "session", "_csrf_token": "csrf"})

        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.content = b'{"refId":"att1","path":"stored/photo.jpg"}'
        response.json.return_value = {"refId": "att1", "path": "stored/photo.jpg"}

        with patch("ticktick_cli.api.v2.httpx.post", return_value=response) as mock_post:
            result = client.upload_task_attachment("proj1", "task1", "att1", path)

        assert result["path"] == "stored/photo.jpg"
        assert mock_post.call_args.args[0].endswith("/attachment/upload/proj1/task1/att1")
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-Csrftoken"] == "csrf"
        assert "Content-Type" not in headers
        files = mock_post.call_args.kwargs["files"]
        assert files["file"][0] == "photo.jpg"

    def test_add_task_attachment_uploads_then_batches(self, tmp_path) -> None:
        path = tmp_path / "photo.jpg"
        path.write_bytes(b"fake image")
        client = V2Client()
        client.get_task = MagicMock(return_value={
            "id": "task1",
            "projectId": "proj1",
            "content": "Existing note",
        })
        client.upload_task_attachment = MagicMock(
            return_value={"refId": "a" * 24, "path": "stored/photo.jpg"}
        )
        client.batch_tasks = MagicMock(return_value={"id2etag": {}})

        with patch("ticktick_cli.api.v2._generate_object_id", return_value="a" * 24):
            result = client.add_task_attachment("task1", path)

        client.upload_task_attachment.assert_called_once_with("proj1", "task1", "a" * 24, path)
        batch_kwargs = client.batch_tasks.call_args.kwargs
        attachment = batch_kwargs["add_attachments"][0]["attachments"][0]
        assert attachment["id"] == "a" * 24
        assert attachment["path"] == "stored/photo.jpg"
        assert attachment["fileType"] == "IMAGE"
        assert batch_kwargs["update"][0]["content"] == (
            f"Existing note\n![image]({'a' * 24}/photo.jpg)"
        )
        assert result["contentLinked"] is True


class TestAttachmentCommands:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_attachment_add_success(self, mock_get: MagicMock, tmp_path) -> None:
        client = _mock_client()
        mock_get.return_value = client
        path = tmp_path / "photo.jpg"
        path.write_bytes(b"fake image")
        client.v2.add_task_attachment.return_value = {
            "attachment": {
                "id": "att1",
                "taskId": "task1",
                "projectId": "proj1",
                "fileName": "photo.jpg",
                "fileType": "IMAGE",
                "size": 10,
                "path": "stored/photo.jpg",
            },
            "markdown": "![image](att1/photo.jpg)",
            "contentLinked": True,
        }

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["attachment", "add", "task1", str(path)],
            obj=_make_ctx(),
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["message"] == "Attachment added."
        assert data["data"]["id"] == "att1"
        assert data["data"]["markdown"] == "![image](att1/photo.jpg)"
        client.v2.add_task_attachment.assert_called_once_with(
            "task1",
            str(path),
            project_id=None,
            insert_content_link=True,
            file_type=None,
        )

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_attachment_add_dry_run(self, mock_get: MagicMock, tmp_path) -> None:
        path = tmp_path / "photo.jpg"
        path.write_bytes(b"fake image")

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["attachment", "add", "task1", str(path)],
            obj=_make_ctx(dry_run=True),
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.attachment.add"
        assert data["details"]["fileType"] == "IMAGE"
        assert data["details"]["markdown"].startswith("![image](")
        mock_get.assert_not_called()

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_attachment_list(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {
            "id": "task1",
            "attachments": [
                {
                    "id": "att1",
                    "fileName": "photo.jpg",
                    "fileType": "IMAGE",
                    "size": 10,
                }
            ],
        }

        runner = CliRunner()
        result = runner.invoke(task_group, ["attachment", "list", "task1"], obj=_make_ctx())

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["data"][0]["fileName"] == "photo.jpg"
        client.v2.get_task.assert_called_once_with("task1")
