# G0 BASELINE FORENSIC SNAPSHOT

时间: 2026-08-21 01:50 (UTC+8)
结论: BASELINE_REGRESSION = 无 (可复现)

git HEAD: 3e07318821d296a9cce4246dbb5060797dadabab @ main
porcelain: 2984 | src modified: 5 (Aug 17 历史遗留)
plist SHA:
  runtime   d92fafbfbed668fb9e5425365bbf364e71e17fa952022d48218395b3cf9f3b5f
  grandslam a01e9c5369c78e771c626ea2e262783cd2d3a3ee79f96df303dd8faaa0037703
launchd: runtime 9251 | grandslam 86067
port 8765: LISTEN (Python 9251)
provider=deepseek model=deepseek-v4-pro mock=false
health: ok | provider_health=healthy | database_health=ok | runtime_state=healthy
db_path: /Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db
DB quick_check: ok | integrity_check: ok
DB schema: conversation_message_index / records / events
stats: total_missions=67 active=40 completed=26 failed=1 blocked=1 pending_approvals=9
  evidence=536 provider_available=true mock_mode=false recovery_state=healthy
recovery: checked=67 resumable=1 duplicate_steps=0
  (mission_da80b3ac43d7 卡 Execution, resumable=true)
conversation_964eaf002f21: 2 messages (真实 deepseek)
mission_ce2a3da481e2: Completed | evidence=16 | receipt=present | eval=passed
evidence root: /Volumes/NEXARA/NEXARA-PRIME/reports
uptime: runtime 48:51 | grandslam 5:25:16 (heartbeat HB#3770 RUNNING incidents=0)
