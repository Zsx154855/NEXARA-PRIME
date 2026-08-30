"""对接冲刺演示种子：通过公共 HTTP API 注入真实数据（只读契约之外的写操作均走既有端点）。

用法：先以独立数据目录启动服务，再运行本脚本：
  PYTHONPATH=src NEXARA_DB_PATH=/tmp/nexara-demo.db NEXARA_MODEL_PROVIDER=mock \\
      NEXARA_MOCK_MODEL=true .venv/bin/python -m uvicorn nexara_prime.api:app \\
      --host 127.0.0.1 --port 8765                             # 终端 A
  .venv/bin/python scripts/seed_experience_demo.py              # 终端 B
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("NEXARA_DEMO_BASE", "http://127.0.0.1:8765")


def call(method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {path} 失败：{exc.code} {exc.read().decode()[:300]}")


def main() -> None:
    health = call("GET", "/health")
    print(f"Runtime: {health['version']} / db={health['database_health']}")

    for objective in (
        "整理本周设计评审纪要并归档",
        "为阳台绿植制定秋季浇水计划",
    ):
        mission = call("POST", "/api/missions", {"objective": objective, "source_dir": None})
        print(f"已创建任务：{mission['mission_id']}（{mission.get('state')}）")

    conversation = call("POST", "/api/conversations", {"title": "对接联调"})
    cid = conversation["conversation_id"]
    call("POST", f"/api/conversations/{cid}/messages", {"content": "体验层对接进展如何？", "idempotency_key": "seed-1"})

    for path in ("/v1/missions", "/v1/conversations", "/v1/session", "/v1/system/status"):
        envelope = call("GET", path)
        assert envelope["success"] is True, f"{path} 信封失败：{envelope}"
        print(f"{path} OK")
    print("种子注入完成。")


if __name__ == "__main__":
    main()
