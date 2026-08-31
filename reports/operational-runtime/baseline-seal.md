# BASELINE SEAL (Operational Runtime V1.0)

- canonical_root: /Volumes/NEXARA/NEXARA-PRIME
- git_head: 3e07318821d296a9cce4246dbb5060797dadabab
- primary_runtime: 8765 (PID 17650, Python 3.12, uptime 8.9h)
- provider: deepseek (status ok)
- primary_database: runtime/nexara.db (quick_check=ok, records=1771)
- 唯一性: 8765 监听=1, 8770 监听=0 (无 shadow runtime)
- event_count: 1938
- recovery: checked=62, resumable=0, completed=24, duplicate_steps=0
- missions: 62 (Completed=24, Failed=1, Approval≈9, Intent≈28)
- api endpoints: 40+ (conversations/missions/approve/run/pause/resume/rollback/
  safe-mode/events/evidence/receipts/memory/knowledge-universe/recovery/adaptive/tools)
- 内盘 1.49GiB · 外盘 474.9GiB

## 已知 Gap 候选（待 scout 确认）
- health 端点缺 version/pid/port/database_health/provider_health/tool_runtime 完整字段
- worktree 2968 改动（多为 build 产物被 git 追踪，历史遗留）
