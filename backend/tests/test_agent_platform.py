import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from google.genai.client import Client as SDKClient
from google.genai import types

from backend import agent_platform as platform


FINDING = {
    "cue_index": 1,
    "candidate_name": "Mara",
    "issue_description": "The name is used before the badge reveal.",
    "proposed_text": "A hooded visitor waits.",
    "evidence_origin": "model_inference",
    "interval_start": 5.0,
    "interval_end": 9.0,
    "uncertainty": "medium",
}


@pytest.fixture
def cloud_mocks(monkeypatch, tmp_path):
    monkeypatch.setattr(platform.config, "GOOGLE_CLOUD_PROJECT", "test-project", raising=False)
    monkeypatch.setattr(platform.config, "GOOGLE_CLOUD_LOCATION", "global", raising=False)
    monkeypatch.setattr(platform.config, "REVEAL_GCS_BUCKET", "test-private-media", raising=False)
    monkeypatch.setattr(platform.config, "GOOGLE_SERVICE_ACCOUNT_JSON", "", raising=False)
    monkeypatch.setattr(platform.config, "REVEAL_MODEL", "gemini-3.6-flash", raising=False)
    credentials = Mock()
    adc = Mock(return_value=(credentials, "test-project"))
    monkeypatch.setattr(platform.google.auth, "default", adc)
    client = MagicMock(spec=SDKClient)
    client.aio = SimpleNamespace(aclose=AsyncMock())
    constructor = Mock(return_value=client)
    monkeypatch.setattr(platform.genai, "Client", constructor)
    storage_client = Mock()
    storage_constructor = Mock(return_value=storage_client)
    monkeypatch.setattr(platform.storage, "Client", storage_constructor)
    blob = storage_client.bucket.return_value.blob.return_value
    sessions = Mock()
    sessions.create_session = AsyncMock()
    sessions.delete_session = AsyncMock()
    monkeypatch.setattr(platform, "InMemorySessionService", Mock(return_value=sessions))
    captured = {}
    result = {"findings": [FINDING]}

    class FakeRunner:
        def __init__(self, **kwargs):
            captured["runner"] = kwargs
        async def run_async(self, **kwargs):
            captured["run"] = kwargs
            if captured.get("failure"):
                raise RuntimeError("Cloud model unavailable")
            yield SimpleNamespace(
                error_code=None,
                error_message=None,
                is_final_response=lambda: True,
                content=types.Content(parts=[types.Part(text=json.dumps(result))]),
            )
        async def close(self):
            captured["runner_closed"] = True

    monkeypatch.setattr(platform, "Runner", FakeRunner)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"mock video bytes")
    return SimpleNamespace(
        video=video, client=client, constructor=constructor, credentials=credentials,
        storage_client=storage_client, storage_constructor=storage_constructor,
        blob=blob, captured=captured, result=result, sessions=sessions, adc=adc,
    )


async def run(mocks, notes='Filmmaker notes containing {untrusted_template}.'):
    return await platform.run_agent_analysis(
        str(mocks.video),
        [{"index": 1, "text": "Mara waits.", "start_seconds": 5.0, "end_seconds": 9.0}],
        notes,
        72.0,
    )


@pytest.mark.asyncio
async def test_agent_uses_enterprise_client_and_gcs_multimodal_input(cloud_mocks):
    m = cloud_mocks
    findings, model = await run(m)
    assert findings == [FINDING]
    assert model == "google-adk/agent-platform/gemini-3.6-flash"
    kwargs = m.constructor.call_args.kwargs
    assert kwargs["enterprise"] is True
    assert kwargs["project"] == "test-project"
    assert kwargs["location"] == "global"
    assert kwargs["credentials"] is m.credentials
    assert "api_key" not in kwargs
    assert kwargs["http_options"].timeout == 60000
    assert kwargs["http_options"].retry_options.attempts == 1
    agent = m.captured["runner"]["agent"]
    assert agent.model.client is m.client
    assert "untrusted_template" not in agent.instruction
    message = m.captured["run"]["new_message"]
    assert message.parts[0].file_data.file_uri.startswith("gs://test-private-media/reveal/")
    assert message.parts[0].file_data.mime_type == "video/mp4"
    assert "untrusted_template" in message.parts[1].text
    assert m.captured["run"]["run_config"].max_llm_calls == 1
    m.blob.upload_from_filename.assert_called_once()
    assert m.blob.upload_from_filename.call_args.kwargs["retry"] is None
    m.blob.delete.assert_called_once()
    m.client.files.upload.assert_not_called()
    m.client.aio.aclose.assert_awaited_once()
    m.client.close.assert_called_once()
    m.sessions.delete_session.assert_awaited_once()
    assert m.captured["runner_closed"]
    m.storage_client.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["upload", "model", "invalid_output"])
async def test_agent_failure_cleans_up_and_does_not_fallback(cloud_mocks, failure):
    m = cloud_mocks
    if failure == "upload":
        m.blob.upload_from_filename.side_effect = RuntimeError("Upload interrupted")
    elif failure == "model":
        m.captured["failure"] = True
    else:
        m.result["findings"] = [{**FINDING, "evidence_origin": "human_verification"}]
    with pytest.raises(Exception):
        await run(m)
    m.blob.delete.assert_called_once()
    m.client.files.upload.assert_not_called()
    m.client.aio.aclose.assert_awaited_once()
    m.storage_client.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("model_fails", [False, True])
async def test_cleanup_failure_does_not_replace_result_or_provider_error(cloud_mocks, model_fails):
    m = cloud_mocks
    m.blob.delete.side_effect = RuntimeError("Deletion unavailable")
    m.captured["failure"] = model_fails
    if model_fails:
        with pytest.raises(RuntimeError, match="Cloud model unavailable"):
            await run(m)
    else:
        findings, _ = await run(m)
        assert findings == [FINDING]
    m.client.aio.aclose.assert_awaited_once()
    m.client.close.assert_called_once()
    m.storage_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_waits_for_upload_before_deleting_object(cloud_mocks):
    m = cloud_mocks
    started, release = threading.Event(), threading.Event()
    def upload(*args, **kwargs):
        started.set()
        assert release.wait(timeout=5)
        m.captured["upload_finished"] = True
    def delete(*args, **kwargs):
        assert m.captured.get("upload_finished") is True
    m.blob.upload_from_filename.side_effect = upload
    m.blob.delete.side_effect = delete
    task = asyncio.create_task(run(m))
    try:
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        m.blob.delete.assert_not_called()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    m.blob.delete.assert_called_once()
    assert "run" not in m.captured
    m.client.aio.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_video_never_creates_cloud_clients(cloud_mocks):
    m = cloud_mocks
    m.video.unlink()
    with pytest.raises(FileNotFoundError):
        await run(m)
    m.constructor.assert_not_called()
    m.storage_constructor.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("info", [
    {"type": "authorized_user", "token_uri": "https://oauth2.googleapis.com/token"},
    {"type": "service_account", "token_uri": "https://unexpected.example/token"},
])
async def test_reject_unexpected_service_account_configuration(cloud_mocks, monkeypatch, info):
    monkeypatch.setattr(platform.config, "GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps(info), raising=False)
    with pytest.raises(ValueError):
        await run(cloud_mocks)
    cloud_mocks.constructor.assert_not_called()
    cloud_mocks.storage_constructor.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_service_account_credentials_override_local_adc(cloud_mocks, monkeypatch):
    m = cloud_mocks
    info = {"type": "service_account", "token_uri": "https://oauth2.googleapis.com/token"}
    monkeypatch.setattr(platform.config, "GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps(info), raising=False)
    factory = Mock(return_value=m.credentials)
    monkeypatch.setattr(platform.service_account.Credentials, "from_service_account_info", factory)
    await run(m)
    factory.assert_called_once_with(info, scopes=platform.CLOUD_SCOPES)
    m.adc.assert_not_called()
    assert m.constructor.call_args.kwargs["credentials"] is m.credentials
    assert m.storage_constructor.call_args.kwargs["credentials"] is m.credentials


@pytest.mark.parametrize("field", ["interval_start", "interval_end"])
def test_output_rejects_nonfinite_intervals(field):
    with pytest.raises(ValueError):
        platform.AnalysisOutput.model_validate({"findings": [{**FINDING, field: float("nan")}]})


@pytest.mark.asyncio
async def test_real_adk_runner_marshals_enterprise_video_request(cloud_mocks, monkeypatch):
    """Exercise ADK and GenAI serialization; intercept HTTP before any network IO."""
    import socket
    import httpx
    from google.auth.credentials import AnonymousCredentials
    from google.adk.runners import Runner as ActualRunner
    from google.adk.sessions import InMemorySessionService as ActualSessions

    m = cloud_mocks
    requests = []
    def reject_network(*args, **kwargs):
        raise AssertionError("The Agent Platform transport test must not open network connections")
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"role": "model", "parts": [{"text": json.dumps({"findings": [FINDING]})}]},
                "finishReason": "STOP",
                "index": 0,
            }],
            "modelVersion": "gemini-3.6-flash",
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20, "totalTokenCount": 30},
        })

    transport = httpx.MockTransport(respond)
    def real_client(**kwargs):
        options = kwargs["http_options"]
        kwargs["http_options"] = options.model_copy(update={
            "async_client_args": {"transport": transport},
            "client_args": {"transport": transport},
        })
        return SDKClient(**kwargs)

    credentials = AnonymousCredentials()
    # GenAI requires a nonempty bearer token even with an intercepted transport.
    # This deliberately invalid token is never sent to a network endpoint.
    credentials.token = "transport-test-only"
    monkeypatch.setattr(platform.genai, "Client", real_client)
    monkeypatch.setattr(platform.google.auth, "default", lambda **kwargs: (credentials, "test-project"))
    monkeypatch.setattr(platform, "Runner", ActualRunner)
    monkeypatch.setattr(platform, "InMemorySessionService", ActualSessions)

    findings, model = await run(m)
    assert findings == [FINDING]
    assert model == "google-adk/agent-platform/gemini-3.6-flash"
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.host == "aiplatform.googleapis.com"
    assert "/projects/test-project/locations/global/publishers/google/models/gemini-3.6-flash:generateContent" in request.url.path
    payload = json.loads(request.content)
    parts = [part for content in payload["contents"] for part in content["parts"]]
    file_parts = [part["fileData"] for part in parts if "fileData" in part]
    object_name = m.storage_client.bucket.return_value.blob.call_args.args[0]
    assert len(file_parts) == 1
    # Protobuf JSON accepts the original field name as well as lowerCamelCase;
    # GenAI currently preserves snake_case fields inside fileData.
    media = file_parts[0]
    assert media.get("fileUri", media.get("file_uri")) == f"gs://test-private-media/{object_name}"
    assert media.get("mimeType", media.get("mime_type")) == "video/mp4"
    assert any("Mara waits." in part.get("text", "") for part in parts)
    generation = payload["generationConfig"]
    assert generation["responseMimeType"] == "application/json"
    schema = generation.get("responseSchema") or generation["responseJsonSchema"]
    finding_schema = schema["properties"]["findings"]["items"]
    assert "cue_index" in finding_schema["required"]
    assert set(finding_schema["properties"]["evidence_origin"]["enum"]) == {
        "model_inference", "dialogue", "filmmaker_intent",
    }
    m.blob.upload_from_filename.assert_called_once()
    m.blob.delete.assert_called_once()
    m.storage_client.close.assert_called_once()
