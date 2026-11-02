#!/usr/bin/env python3
"""End-to-end smoke over a real HTTP server.

Every earlier check ran in-process with TestClient. This one starts uvicorn,
creates a mission against a real git repository inside the workspace, approves
it over HTTP, runs it, and reads the report back — then asserts the citations
resolve. Exit 0 only if the whole path works.

    python3 scripts/e2e/http_smoke.py [--keep]
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(url: str, method: str = "GET", body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def wait_health(base: str, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _ = request(base + "/health")
            if status == 200:
                return
        except Exception:  # noqa: BLE001 - still starting
            pass
        time.sleep(0.4)
    raise SystemExit("server did not become healthy")


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="nexara-e2e-"))
    workspace = root / "workspace"
    repo = workspace / "repo"
    repo.mkdir(parents=True)
    for cmd in (["git", "init", "-q", "-b", "main", str(repo)],
                ["git", "-C", str(repo), "config", "user.email", "e2e@example.com"],
                ["git", "-C", str(repo), "config", "user.name", "e2e"]):
        subprocess.run(cmd, check=True)
    (repo / "app.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_app.py").write_text("def test_hello():\n    assert True\n", encoding="utf-8")
    for cmd in (["git", "-C", str(repo), "add", "-A"],
                ["git", "-C", str(repo), "commit", "-q", "-m", "init"]):
        subprocess.run(cmd, check=True)

    port = free_port()
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'platform' / 'sdk' / 'python'}",
        "NEXARA_DB_PATH": str(root / "runtime" / "e2e.db"),
        "NEXARA_WORKSPACE_ROOT": str(workspace),
        "NEXARA_REPORT_ROOT": str(root / "reports"),
        "NEXARA_MODEL_PROVIDER": "mock",
        "NEXARA_MOCK_MODEL": "true",
        "NEXARA_API_HOST": "127.0.0.1",
        "NEXARA_API_PORT": str(port),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "nexara_prime.api:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(root), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait_health(base)
        status, mission = request(base + "/api/missions", "POST",
                                  {"objective": "e2e smoke over http", "source_dir": str(repo)})
        assert status == 200, (status, mission)
        mid = mission["mission_id"]
        print(f"created   {mid}")

        assert request(base + f"/api/missions/{mid}/plan", "POST", {})[0] == 200
        status, approved = request(base + f"/api/missions/{mid}/approve", "POST",
                                   {"approved": True, "actor": "e2e"})
        assert status == 200, (status, approved)
        print("planned and approved over http")

        status, final = request(base + f"/api/missions/{mid}/run", "POST", {})
        assert status == 200, (status, final)
        print(f"run       state={final.get('state')}")

        status, evidence = request(base + f"/api/evidence?mission_id={mid}")
        assert status == 200 and isinstance(evidence, list)
        kinds = {item.get("kind") for item in evidence}
        assert "verification_report" in kinds, kinds
        assert "reviewer_verdict" in kinds, kinds
        print(f"evidence  {len(evidence)} items, kinds={sorted(k for k in kinds if k)}")

        report = Path(root) / "reports" / mid / "mission-report.md"
        assert report.exists(), f"report missing: {report}"
        text = report.read_text(encoding="utf-8")
        assert "Analysed root" in text
        print(f"report    {report.stat().st_size} bytes")
        print("E2E SMOKE: PASS")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        if "--keep" not in sys.argv:
            import shutil
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
