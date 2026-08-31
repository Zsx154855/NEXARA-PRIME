# SESSION + MEMORY PERSISTENCE — 真实验证

## Session (SQLiteSessionStore)
- 新增 L2: src/nexara_prime/session_persistence.py (接 SQLiteStore, record_type="session")
- 真实 SQLite 持久化: session_8847f8bd6f9c 写入 records 表 ✓
- restart 恢复: 重新开 store → same session_id + same conversation_ids + version=2 ✓
- SESSION_PERSISTENCE=PASS, SESSION_RESTART_RECOVERY=PASS

## Memory ARCHIVED (MemoryArchive + 真实 SQLite)
- Memory A (FACT, key=gap-closure-mem) → committed
- Memory B (同 key) → A 自动 superseded (superseded_by=B) ✓
- archive A → archived (archived_at set, archive_reason set, superseded_by=B) ✓
- restart → A=archived (archived_at/superseded_by 保留), B=committed ✓
- retrieval: list_active 排除 archived ✓, A 在 list_archived ✓
- MEMORY_PERSISTENCE=PASS, MEMORY_RESTART_RECOVERY=PASS, ARCHIVED_RETRIEVAL_POLICY=PASS

## 证据文件
- verify_session_persistence.py (真实 DB 验证脚本)
- verify_memory_persistence.py (真实 DB 验证脚本)
- 输出见本目录同名 .py 的运行结果
