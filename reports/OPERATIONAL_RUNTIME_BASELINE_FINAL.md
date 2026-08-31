# NEXARA V1.0 OPERATIONAL RUNTIME BASELINE

封存时间：2026-08-21 01:05 (UTC+8)
封存性质：只读封存（未修改任何 Core / Runtime / DB / UI / Provider / Mission / Governance）
状态：VERIFIED — 所有 PASS 项均由真实磁盘 / API / mission / evidence 结果支撑，无 Mock 冒充 Real。

---

## 1. launchd 进程

| Job | PID | 状态 | 退出码 |
|-----|-----|------|--------|
| com.nexara.runtime | 9251 | 运行中 | 端口 8765 LISTEN（-15 为 kickstart -k 的 SIGTERM 历史退出码） |
| com.nexara.grandslam.supervisor | 86067 | 运行中 | 0 |

端口确认：`Python 9251 ... TCP 127.0.0.1:8765 (LISTEN)`

## 2. Runtime Endpoint / Provider / Model

```
endpoint        : http://127.0.0.1:8765
status          : ok
provider        : deepseek
provider_health : healthy
model           : deepseek-v4-pro
mock            : false
db_path         : /Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db
runtime_state   : healthy
version         : 0.1.0
event_count     : 2204
```

进程 env 实测（`ps eww -p 9251`）：
- NEXARA_MODEL_PROVIDER=deepseek
- NEXARA_MOCK_MODEL=false
- NEXARA_MODEL_NAME=deepseek-v4-pro
- NEXARA_MODEL_ENDPOINT=https://api.deepseek.com/v1
- NEXARA_MODEL_TIMEOUT=120
- NEXARA_MAX_OUTPUT_TOKENS=4096
- NEXARA_DB_PATH=/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db

进程 cwd：`/Volumes/NEXARA/NEXARA-PRIME`
db 句柄：`3u /Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db`（外盘）

## 3. Real Conversation Evidence

- conversation_id：`conversation_964eaf002f21`
- 用户消息：「你好，请用一句话介绍 NEXARA 是什么。」
- 助手回复（真实推理，非 mock）：
  > NEXARA 是一个由用户第一方治理的运行时，用于安全、可控地执行任务和对话。
- metadata：provider=deepseek · model=deepseek-v4-pro · latency_ms=3439.79 · intent=chat · intent_confidence=0.9

## 4. Real Mission Evidence

- mission_id：`mission_ce2a3da481e2`
- objective：「launchd runtime 验证：执行一次运行时健康检查并生成简短报告」
- current_state：Completed
- evidence_count：16
- receipt_status：present
- evaluation_status：passed
- memory_patch_status：patched
- provider：deepseek
- approval_status：consumed

外盘 db mission 总数：67（封存时）

## 5. Graceful Restart Evidence

- 动作：`launchctl kickstart -k gui/$(id -u)/com.nexara.runtime`（SIGTERM 优雅重启，非 -9）
- 重启前 PID：8990 → 重启后 PID：9251
- health 恢复：ok / provider=deepseek / db_path=外盘
- mission continuity：`mission_ce2a3da481e2` 保持 Completed / evidence_count=16 / receipt_status=present（持久化未丢）

## 6. plist SHA256

```
d92fafbfbed668fb9e5425365bbf364e71e17fa952022d48218395b3cf9f3b5f  com.nexara.runtime.plist
a01e9c5369c78e771c626ea2e262783cd2d3a3ee79f96df303dd8faaa0037703  com.nexara.grandslam.supervisor.plist
```

回滚点保留：`~/Library/LaunchAgents/*.bak-20260820-202315`

## 7. Git HEAD / diff

- HEAD：`3e07318821d296a9cce4246dbb5060797dadabab`
- branch：`main`
- remote：`https://github.com/Zsx154855/NEXARA-PRIME.git`
- src/nexara_prime 本轮改动：**0**（5 个 M 文件 mtime 为 Aug 17 18:30-18:38，迁移前历史 dirty 状态，非本轮）
- git status --porcelain：2983（历史 dirty 状态）

## 8. DB Schema

- 表结构：`conversation_message_index` / `records` / `events`（未改）

## 9. 最终判定

| 判定项 | 结果 |
|--------|------|
| OPERATIONAL_RUNTIME | PASS |
| LAUNCHD_RUNTIME | PASS |
| REAL_CONVERSATION | PASS |
| MISSION | PASS |
| GRACEFUL_RESTART | PASS |
| CORE_RUNTIME_DRIFT | NONE |

NO-FALSE-PASS 核验：
- Mock ≠ Real：✓ 排除（provider=deepseek、mock=false、真实 latency_ms/token 统计、真实上下文响应）
- Build ≠ Runtime：✓ 以真实监听端口 + health + mission 为准
- Test Exists ≠ Test Passed：✓ 以真实 mission Completed + evidence=16 为准
- Process Running ≠ Operational：✓ 以真实 conversation + mission 全链路为准
