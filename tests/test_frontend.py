import io

import httpx


def test_api_client_submits_inputs_and_idempotency_key():
    from frontend.api_client import APIClient, APIError
    def handle(request):
        if request.url.path == "/api/uploads":
            assert b"clip.mp4" in request.content
            return httpx.Response(201, json={"upload_id": "u"})
        if request.url.path == "/api/jobs":
            assert request.headers["Idempotency-Key"] == "run123"
            assert b'"n_people":2' in request.content
            return httpx.Response(202, json={"job_id": "j"})
        return httpx.Response(200, json={"status": "queued"})
    client = APIClient("http://test", transport=httpx.MockTransport(handle))
    assert client.upload(io.BytesIO(b"video"), "clip.mp4")["upload_id"] == "u"
    assert client.submit(dict(upload_id="u", n_people=2, threshold_seconds=1, polygon=[]), "run123")["job_id"] == "j"
    assert client.status("j")["status"] == "queued"


def test_api_client_reports_validation_errors_in_plain_text():
    from frontend.api_client import APIClient, APIError
    import pytest
    client = APIClient("http://test", transport=httpx.MockTransport(lambda r: httpx.Response(422, json={"detail": "Polygon edges must not cross."})))
    with pytest.raises(APIError, match="Polygon edges must not cross"):
        client.submit({}, "key")


def test_polling_is_only_enabled_for_known_short_active_videos():
    from frontend.state import polling_interval
    assert polling_interval(29.9, "queued") == 7
    assert polling_interval(30, "processing") is None
    assert polling_interval(None, "processing") is None
    assert polling_interval(10, "succeeded") is None
    assert polling_interval(10, "failed") is None


def test_retry_key_survives_reruns_but_changes_for_new_inputs():
    from frontend.state import submission_key
    state = {}
    first = submission_key(state, {"upload_id": "u", "n_people": 2})
    assert submission_key(state, {"n_people": 2, "upload_id": "u"}) == first
    assert submission_key(state, {"upload_id": "u", "n_people": 3}) != first


def test_streamlit_app_starts_without_a_running_backend():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "frontend/app.py")).run()
    assert not app.exception
    assert any("People in Zone" in title.value for title in app.title)
