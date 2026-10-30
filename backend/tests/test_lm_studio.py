import json
from types import SimpleNamespace
import pytest
from app.services.providers import lm_studio as local


def test_local_request_uses_local_model_without_cloud_credentials(monkeypatch):
    monkeypatch.setattr(local, "LM_STUDIO_MODEL", "local-model")
    monkeypatch.setattr(local, "LM_STUDIO_API_KEY", "")
    captured = {}
    def request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return SimpleNamespace(body=json.dumps({"choices": [{"message": {"content": "answer"}}]}).encode())
    monkeypatch.setattr(local._HTTP, "request", request)
    client = local.LMStudioClient()
    assert client.complete("question", system_prompt="system", temperature=0, max_tokens=50) == "answer"
    assert captured["url"].endswith("/v1/chat/completions")
    assert "Authorization" not in captured["headers"]
    assert json.loads(captured["body"])["model"] == "local-model"


def test_local_model_required(monkeypatch):
    monkeypatch.setattr(local, "LM_STUDIO_MODEL", "")
    with pytest.raises(local.LMStudioError):
        local.LMStudioClient()
