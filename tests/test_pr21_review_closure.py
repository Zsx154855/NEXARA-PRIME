from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.models import MemoryKind
from nexara_prime.model_gateway import OpenAICompatibleProvider
from nexara_prime.real_context import RealRepositoryContext
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
    assert captured["payload"]["metadata"] == {"nexara_context_hash": "hash-1"}
    assert all(isinstance(value, str) for value in captured["payload"]["metadata"].values())


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


def test_repository_context_redacts_secret_values_from_excerpts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    credential_field = "client_" + "secret"
    secret_value = "super-" + "secret-" + "value"
    (repo / "settings.py").write_text(credential_field + ' = "' + secret_value + '"\n', encoding="utf-8")
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@nexara.local"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "NEXARA Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "settings.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)

    context = RealRepositoryContext().collect(repo)
    excerpt = context.excerpts["settings.py"]
    assert secret_value not in excerpt
    assert "[REDACTED]" in excerpt


def test_memory_fact_without_evidence_is_not_a_binding_violation(tmp_path: Path) -> None:
    runtime = NexaraRuntime(Settings(
        db_path=tmp_path / "test.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    ))
    mission = runtime.create_mission("Memory fact binding")
    runtime.memory.write(MemoryKind.FACT, "repository.language", "Python", "trace", mission.mission_id)

    report = runtime.memory.verify_evidence_binding(mission.mission_id)
    assert report["all_bound"] is True
    assert report["exempt"] == 1


def test_receipt_chain_fails_when_tool_envelope_is_corrupt(tmp_path: Path) -> None:
    runtime = NexaraRuntime(Settings(
        db_path=tmp_path / "test.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    ))
    mission = runtime.create_mission("Corrupt tool envelope")
    with pytest.raises(KeyError):
        runtime.tools.invoke(mission.mission_id, "missing_tool", {}, "trace")
    first = runtime.evidence.verify_receipt_chain(mission.mission_id)
    assert first["chain_intact"] is True

    tool_id = first["chain"][0]["invocation_id"]
    with runtime.store._lock, runtime.store._conn:
        runtime.store._conn.execute(
            "UPDATE records SET integrity_sha256=? WHERE record_id=?",
            ("corrupt", tool_id),
        )
    corrupt = runtime.evidence.verify_receipt_chain(mission.mission_id)
    assert corrupt["chain_intact"] is False
    assert corrupt["corrupt_tool_records"] == [tool_id]


def test_api_mutations_return_snapshots_with_plan(tmp_path: Path) -> None:
    runtime = NexaraRuntime(Settings(
        db_path=tmp_path / "test.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    ))
    app = create_app(runtime)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    created = client.post("/api/missions", json={"objective": "Snapshot API"}).json()
    mission_id = created["mission_id"]
    planned = client.post(f"/api/missions/{mission_id}/plan").json()
    assert planned["title"] == "Snapshot API"
    assert planned["plan"]["steps"]
    assert planned["approval_status"] == "pending"
    paused = client.post(f"/api/missions/{mission_id}/pause").json()
    assert paused["title"] == "Snapshot API"
    assert paused["paused"] is True
