from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.model_gateway import OpenAICompatibleProvider
from nexara_prime.runtime import NexaraRuntime


def test_openai_compatible_provider_sends_excerpts_as_model_visible_message(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self) -> bytes:
            return json.dumps({
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr("nexara_prime.model_gateway.urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider("https://provider.example/v1", api_key="test-key")
    provider.complete(
        "system",
        "task",
        {
            "context_hash": "hash-1",
            "repository": "/repo",
            "branch": "main",
            "head_sha": "abc",
            "dirty": False,
            "files": [{"path": "README.md", "sha256": "abc"}],
            "excerpts": [{"path": "README.md", "text": "visible repo excerpt"}],
        },
        trace_id="trace",
    )

    messages = captured["payload"]["messages"]
    assert any("visible repo excerpt" in message["content"] for message in messages)
    assert captured["payload"]["metadata"]["nexara_context_hash"] == "hash-1"


def test_console_route_is_not_mounted_without_next_export() -> None:
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    app = create_app(NexaraRuntime(settings))
    route_names = {getattr(route, "name", "") for route in app.routes}
    assert "console" not in route_names
