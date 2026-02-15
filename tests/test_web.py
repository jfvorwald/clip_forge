"""Unit tests for the ClipForge web UI."""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clipforge.web import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app(work_dir=tmp_path)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _upload(client, filename="test.mp4", content=b"fake video data"):
    return client.post(
        "/api/upload",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


class TestIndex:
    def test_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"ClipForge" in resp.data


class TestUpload:
    def test_upload_success(self, client, tmp_path):
        resp = _upload(client)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "job_id" in data
        assert data["filename"] == "test.mp4"

    def test_upload_no_file(self, client):
        resp = client.post("/api/upload")
        assert resp.status_code == 400

    def test_upload_creates_file(self, client, tmp_path):
        resp = _upload(client, content=b"CONTENT")
        job_id = resp.get_json()["job_id"]
        input_file = tmp_path / job_id / "input.mp4"
        assert input_file.exists()
        assert input_file.read_bytes() == b"CONTENT"


class TestProcess:
    def test_process_unknown_job(self, client):
        resp = client.post(
            "/api/jobs/nonexistent/process",
            json={"silence_cut": {"enabled": True}},
        )
        assert resp.status_code == 404

    @patch("clipforge.web.routes.process")
    def test_process_starts(self, mock_process, client):
        mock_result = MagicMock()
        mock_result.output_path = Path("/tmp/out.mp4")
        mock_result.duration_original = 22.0
        mock_result.duration_final = 15.0
        mock_result.segments_removed = 3
        mock_process.return_value = mock_result

        upload_resp = _upload(client)
        job_id = upload_resp.get_json()["job_id"]

        resp = client.post(
            f"/api/jobs/{job_id}/process",
            json={"silence_cut": {"enabled": True}},
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "started"


class TestStatus:
    def test_status_after_upload(self, client):
        upload_resp = _upload(client)
        job_id = upload_resp.get_json()["job_id"]

        resp = client.get(f"/api/jobs/{job_id}/status")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "uploaded"

    def test_status_unknown_job(self, client):
        resp = client.get("/api/jobs/nonexistent/status")
        assert resp.status_code == 404


class TestDownload:
    def test_download_not_complete(self, client):
        upload_resp = _upload(client)
        job_id = upload_resp.get_json()["job_id"]

        resp = client.get(f"/api/jobs/{job_id}/result")
        assert resp.status_code == 409

    def test_download_unknown_job(self, client):
        resp = client.get("/api/jobs/nonexistent/result")
        assert resp.status_code == 404
