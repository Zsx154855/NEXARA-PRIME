# PHASE 7 STABILITY WINDOW (真实 30min)

窗口: 2026-08-21 12:12:43 → 12:42:56 (1800s, 60 样本 @30s)

结果:
- health: 60/60 全部 ok (无 crash, 无降级)
- CPU: 5-27% (稳定, 无异常飙升)
- 内存: 0.5-1.0% (稳定, 无泄漏; rss 45-82MB 波动后稳定在 67MB)
- dbsize: 5451776 bytes 全程稳定 (无异常增长)
- events: 2417→2420 (真实负载增长)
- missions: 70 稳定
- PID 变化 (59750→63750→63990): 为本任务期间 upgrade/rollback 主动重启, 非 crash

判定: STABILITY = PASS (真实 30min 窗口, 非声称"长期稳定")
