import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import backend.analyzer as analyzer


@pytest.mark.asyncio
async def test_cloud_mode_uses_agent_even_with_developer_key(monkeypatch):
    agent = AsyncMock(return_value=([], "google-adk/agent-platform/test-model"))
    developer = AsyncMock(side_effect=AssertionError("Wrong provider"))
    monkeypatch.setitem(sys.modules, "backend.agent_platform", SimpleNamespace(run_agent_analysis=agent))
    monkeypatch.setattr(analyzer, "REVEAL_PROVIDER", "agent_platform")
    monkeypatch.setattr(analyzer, "GEMINI_API_KEY", "unused-test-key")
    monkeypatch.setattr(analyzer, "_run_gemini_analysis_threaded", developer)
    findings, provider = await analyzer.analyze_review("clip.mp4", [])
    assert findings == []
    assert provider == "google-adk/agent-platform/test-model"
    agent.assert_awaited_once()
    developer.assert_not_awaited()


@pytest.mark.asyncio
async def test_cloud_failure_never_becomes_offline_success(monkeypatch):
    agent = AsyncMock(side_effect=RuntimeError("Cloud permission denied"))
    monkeypatch.setitem(sys.modules, "backend.agent_platform", SimpleNamespace(run_agent_analysis=agent))
    monkeypatch.setattr(analyzer, "REVEAL_PROVIDER", "agent_platform")
    monkeypatch.setattr(analyzer, "GEMINI_API_KEY", "unused-test-key")
    with pytest.raises(RuntimeError, match="Cloud permission denied"):
        await analyzer.analyze_review("clip.mp4", [])


@pytest.mark.asyncio
async def test_auto_keeps_existing_developer_api_configuration(monkeypatch):
    developer = AsyncMock(return_value=([], "google-genai/test-model"))
    monkeypatch.setattr(analyzer, "REVEAL_PROVIDER", "auto")
    monkeypatch.setattr(analyzer, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(analyzer, "GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setattr(analyzer, "_run_gemini_analysis_threaded", developer)
    assert await analyzer.analyze_review("clip.mp4", []) == ([], "google-genai/test-model")
    developer.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["unknown", "developer_api"])
async def test_invalid_or_missing_provider_configuration_fails(monkeypatch, provider):
    monkeypatch.setattr(analyzer, "REVEAL_PROVIDER", provider)
    monkeypatch.setattr(analyzer, "GEMINI_API_KEY", "")
    with pytest.raises((RuntimeError, ValueError)):
        await analyzer.analyze_review("clip.mp4", [])


def test_both_providers_reject_unknown_cues_and_invalid_evidence():
    cues = [{"index": 3, "end_seconds": 10}]
    valid = {"cue_index": 3, "interval_start": 1, "interval_end": 5}
    records = [valid, {**valid, "cue_index": 2}, {**valid, "cue_index": "nan"},
               {**valid, "interval_start": float("nan")}, {**valid, "interval_end": 99}, None]
    results = analyzer.validate_findings(records, cues, 10)
    assert len(results) == 1
    assert results[0].cue_index == 3
